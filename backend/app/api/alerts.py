"""
Alerts API — GET /api/v1/alerts
Returns temporal poller events for a workspace.
Also exposes SSE stream for real-time alert push via Redis pub/sub.
"""
from __future__ import annotations
import asyncio
import json
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import get_settings

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])
settings = get_settings()


class AlertEvent(BaseModel):
    id: str
    signal_type: str
    tool_name: str
    threshold_rule: str
    alert_fired: bool
    checked_at: str
    alert_sent_at: str | None = None
    triggered_run_id: str | None = None


@router.get("", response_model=list[AlertEvent])
async def get_alerts(
    workspace_id: str | None = Query(default=None),
    limit: int = Query(default=20, le=100),
    unfired_only: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
):
    """Return recent temporal poller alerts."""
    where_clauses = []
    params: dict = {"limit": limit}

    if workspace_id:
        where_clauses.append("workspace_id = :workspace_id")
        params["workspace_id"] = workspace_id
    if unfired_only:
        where_clauses.append("alert_fired = false")

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    result = await db.execute(
        text(f"""
            SELECT id::text, signal_type, tool_name, threshold_rule,
                   alert_fired, checked_at::text, alert_sent_at::text, triggered_run_id::text
            FROM temporal_poller_events
            {where_sql}
            ORDER BY checked_at DESC
            LIMIT :limit
        """),
        params,
    )
    rows = result.fetchall()
    return [AlertEvent(**dict(row._mapping)) for row in rows]


@router.get("/stream")
async def stream_alerts():
    """
    SSE stream — pushes alerts in real time via Redis pub/sub.
    Frontend subscribes to this endpoint to receive live notifications.
    """
    async def generator() -> AsyncGenerator[str, None]:
        try:
            import redis.asyncio as aioredis
            r = aioredis.from_url(settings.redis_url)
            pubsub = r.pubsub()
            await pubsub.subscribe("temporal_alerts")

            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=30)
                if message and message.get("type") == "message":
                    yield f"data: {message['data'].decode()}\n\n"
                else:
                    # Heartbeat — keeps connection alive
                    yield ": heartbeat\n\n"
                    await asyncio.sleep(15)

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
