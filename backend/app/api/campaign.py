"""
Campaign API — endpoints for full growth loop invocation.

POST /api/v1/campaign          — runs full supervisor graph (research → content → campaign)
POST /api/v1/campaign/stream   — SSE streaming version
GET  /api/v1/campaign/signals/recent  — recent growth signals across all campaigns (workspace overview)
GET  /api/v1/campaign/{id}     — fetch campaign + performance summary
GET  /api/v1/campaign/{id}/signals — fetch growth signals for a campaign
"""
from __future__ import annotations
import asyncio
import json
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import text

from app.core.database import get_db

router = APIRouter(prefix="/api/v1/campaign", tags=["campaign"])


# ─────────────────────────────────────────────────────────────────────────────
# Request schema
# ─────────────────────────────────────────────────────────────────────────────

class CampaignRequest(BaseModel):
    query: str
    workspace_id: str = ""
    route: str = "full_campaign"    # research_only | research_content | full_campaign
    platforms: list[str] = ["linkedin"]


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/v1/campaign — blocking
# ─────────────────────────────────────────────────────────────────────────────

@router.post("")
async def run_campaign(req: CampaignRequest):
    from app.agents.supervisor_graph import supervisor_graph

    campaign_id = str(uuid.uuid4())
    result = await supervisor_graph.ainvoke({
        "user_query": req.query,
        "workspace_id": req.workspace_id,
        "campaign_id": campaign_id,
        "route": req.route,
    })

    return {
        "campaign_id": campaign_id,
        "route": result.get("route"),
        "plan": result.get("plan"),
        "status": result.get("status"),
        "growth_signals": result.get("campaign_result", {}).get("growth_signals", []),
        "kb_write": result.get("campaign_result", {}).get("kb_write_result", {}),
    }


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/v1/campaign/stream — SSE
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/stream")
async def stream_campaign(req: CampaignRequest):
    from app.agents.supervisor_graph import supervisor_graph

    campaign_id = str(uuid.uuid4())

    async def event_stream() -> AsyncGenerator[str, None]:
        yield _sse("start", {"campaign_id": campaign_id, "query": req.query})

        try:
            async for event in supervisor_graph.astream_events(
                {
                    "user_query": req.query,
                    "workspace_id": req.workspace_id,
                    "campaign_id": campaign_id,
                    "route": req.route,
                },
                version="v2",
            ):
                kind = event.get("event", "")
                name = event.get("name", "")

                if kind == "on_chain_start":
                    yield _sse("node_start", {"node": name})
                elif kind == "on_chain_end":
                    output = event.get("data", {}).get("output", {})
                    yield _sse("node_end", {"node": name, "status": output.get("status", "")})

        except Exception as e:
            yield _sse("error", {"message": str(e)})

        yield _sse("done", {"campaign_id": campaign_id})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v1/campaign/signals/recent
# Returns the N most-recent growth signals across all campaigns.
# Used by the workspace overview page.
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/signals/recent")
async def get_recent_signals(limit: int = 20, db=Depends(get_db)):
    result = await db.execute(
        text("""
            SELECT
                gs.id,
                gs.campaign_id,
                c.name  AS campaign_name,
                gs.signal_type,
                gs.description,
                gs.magnitude,
                gs.confidence,
                gs.metric,
                gs.affected_variable,
                gs.audience_segment,
                gs.content_attributes,
                gs.created_at
            FROM growth_signals gs
            LEFT JOIN campaigns c ON c.id = gs.campaign_id
            ORDER BY gs.created_at DESC
            LIMIT :limit
        """),
        {"limit": min(limit, 100)},
    )
    rows = [dict(r) for r in result.mappings().all()]

    # Shape into signal_map ui_payload buckets expected by the frontend card
    signal_types: dict[str, list] = {}
    for row in rows:
        stype = row.get("signal_type", "other")
        signal_types.setdefault(stype, []).append(row)

    # Build a compact signals list for the signal_map card
    signals = []
    for stype, items in signal_types.items():
        best = max(items, key=lambda r: float(r.get("confidence") or 0))
        signals.append({
            "label": stype.replace("_", " ").title(),
            "value": round(float(best.get("magnitude") or 0) * 100, 1),
            "trend": f"{round(float(best.get('confidence') or 0) * 100, 0):.0f}% confidence",
            "description": best.get("description", ""),
        })

    return {
        "signals": signals,
        "raw": rows,
        "total": len(rows),
    }


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v1/campaign/{id}
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{campaign_id}")
async def get_campaign(campaign_id: str, db=Depends(get_db)):
    result = await db.execute(
        text("SELECT * FROM campaigns WHERE id = :id"),
        {"id": campaign_id},
    )
    row = result.mappings().first()
    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Campaign not found")

    summary = await db.execute(
        text("SELECT * FROM campaign_performance_summary WHERE campaign_id = :id"),
        {"id": campaign_id},
    )
    summary_row = summary.mappings().first()

    return {
        "campaign": dict(row),
        "performance": dict(summary_row) if summary_row else None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v1/campaign/{id}/signals
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{campaign_id}/signals")
async def get_growth_signals(campaign_id: str, db=Depends(get_db)):
    result = await db.execute(
        text("""
            SELECT * FROM growth_signals
            WHERE campaign_id = :id
            ORDER BY confidence DESC, magnitude DESC
        """),
        {"id": campaign_id},
    )
    return {"signals": [dict(r) for r in result.mappings().all()]}


# ─────────────────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────────────────

def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"
