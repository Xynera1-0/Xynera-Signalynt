"""
Research API — POST /api/v1/research
Invokes the LangGraph research graph and streams progress via SSE.
"""
from __future__ import annotations
import json
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import get_settings
from app.agents.research_graph import research_graph
from app.agents.schemas import UserReport, ContentBrief

router = APIRouter(prefix="/api/v1/research", tags=["research"])
settings = get_settings()


class ResearchRequest(BaseModel):
    query: str
    workspace_context: dict = {}
    routing: str = "to_user"           # "to_user" | "to_content_agent"
    thread_id: str | None = None        # omit to start a new session


class ResearchResponse(BaseModel):
    thread_id: str
    user_report: UserReport | None = None
    content_brief: ContentBrief | None = None


@router.post("", response_model=ResearchResponse)
async def run_research(
    request: ResearchRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Run a research sweep. Blocks until complete, returns full report.
    Use /stream for progressive output.
    """
    thread_id = request.thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "user_query": request.query,
        "workspace_context": request.workspace_context,
        "routing": request.routing,
        "agent_findings": [],
        "alert_context": None,
        "orchestrator_plan": None,
        "synthesis_result": None,
        "user_report": None,
        "content_brief": None,
    }

    try:
        result = await research_graph.ainvoke(initial_state, config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Research graph failed: {str(e)}")

    return ResearchResponse(
        thread_id=thread_id,
        user_report=result.get("user_report"),
        content_brief=result.get("content_brief"),
    )


@router.post("/stream")
async def stream_research(request: ResearchRequest):
    """
    Stream research progress as Server-Sent Events.
    Each event is a JSON payload with {event, data}.
    """
    thread_id = request.thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "user_query": request.query,
        "workspace_context": request.workspace_context,
        "routing": request.routing,
        "agent_findings": [],
        "alert_context": None,
        "orchestrator_plan": None,
        "synthesis_result": None,
        "user_report": None,
        "content_brief": None,
    }

    async def event_generator() -> AsyncGenerator[str, None]:
        yield _sse("start", {"thread_id": thread_id, "query": request.query})

        try:
            async for chunk in research_graph.astream(initial_state, config, stream_mode="updates"):
                for node_name, node_output in chunk.items():
                    yield _sse("node_complete", {
                        "node": node_name,
                        "has_findings": bool(node_output.get("agent_findings")),
                    })

            # Fetch final state
            final = await research_graph.aget_state(config)
            values = final.values if hasattr(final, "values") else {}

            yield _sse("complete", {
                "thread_id": thread_id,
                "user_report": values.get("user_report"),
                "content_brief": values.get("content_brief"),
            })

        except Exception as e:
            yield _sse("error", {"message": str(e)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"
