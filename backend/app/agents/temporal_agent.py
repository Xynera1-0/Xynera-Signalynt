"""
Temporal Intelligence Agent — compiled subgraph, dual-mode.
Called by: research graph (ambient_context) and content graph (publish_timing).
"""
from __future__ import annotations
from datetime import datetime, timezone

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from app.agents.base import get_llm
from app.agents.prompts import TEMPORAL_AGENT_AMBIENT_PROMPT, TEMPORAL_AGENT_PUBLISH_PROMPT
from app.tools.registry import get_tools_for

AGENT_NAME = "temporal_agent"


class TemporalState(BaseModel):
    topic: str = ""
    mode: str = "ambient_context"    # ambient_context | publish_timing
    platform: str = ""
    content_summary: str = ""
    result: dict = {}


async def temporal_agent_node(state: TemporalState) -> dict:
    tools = get_tools_for(AGENT_NAME)
    llm = get_llm(temperature=0.3)

    tool_results = []

    if "pytrends_interest" in tools:
        keywords = state.topic.split()[:3]
        results = await tools["pytrends_interest"](keywords, timeframe="now 7-d")
        tool_results.extend(results)

    if "newsapi_headlines" in tools:
        results = await tools["newsapi_headlines"](state.topic, days_back=3)
        tool_results.extend(results)

    if "calendarific_events" in tools:
        now = datetime.now(timezone.utc)
        results = await tools["calendarific_events"](year=now.year, month=now.month)
        tool_results.extend(results)

    platform_timing = ""
    if state.mode == "publish_timing" and "platform_timing_heuristics" in tools:
        timing = tools["platform_timing_heuristics"](state.platform or "linkedin")
        platform_timing = timing.content

    if "exa_search" in tools:
        results = await tools["exa_search"](f"{state.topic} trending news this week", num_results=3)
        tool_results.extend(results)

    tool_context = "\n\n".join(
        f"[{r.tool_name}] {r.source_name or ''}\n{r.content[:500]}"
        for r in tool_results if not r.error and r.content
    )

    if state.mode == "publish_timing":
        prompt_text = TEMPORAL_AGENT_PUBLISH_PROMPT.format(
            platform=state.platform,
            content_summary=state.content_summary,
            topic=state.topic,
        )
    else:
        prompt_text = TEMPORAL_AGENT_AMBIENT_PROMPT.format(topic=state.topic)

    full_prompt = f"{prompt_text}\n\nCURRENT TEMPORAL DATA:\n{tool_context[:6000]}"
    if platform_timing:
        full_prompt += f"\n\nPLATFORM TIMING:\n{platform_timing}"

    response = await llm.ainvoke([HumanMessage(content=full_prompt)])
    llm_text = response.content if hasattr(response, "content") else str(response)

    return {"result": {"mode": state.mode, "analysis": llm_text, "timestamp": datetime.now(timezone.utc).isoformat()}}


# Build and compile the subgraph
def build_temporal_agent():
    builder = StateGraph(TemporalState)
    builder.add_node("temporal_agent", temporal_agent_node)
    builder.set_entry_point("temporal_agent")
    builder.add_edge("temporal_agent", END)
    return builder.compile()


temporal_agent = build_temporal_agent()


# Node wrapper for use inside research graph via Send()
async def temporal_agent_research_node(state: dict) -> dict:
    topic = state.get("topic", state.get("user_query", ""))
    result = await temporal_agent.ainvoke(TemporalState(topic=topic, mode="ambient_context"))
    return {"agent_findings": []}   # temporal context injected into state separately


# Standalone call for content graph
async def get_publish_timing(topic: str, platform: str, content_summary: str) -> dict:
    result = await temporal_agent.ainvoke(
        TemporalState(topic=topic, mode="publish_timing", platform=platform, content_summary=content_summary)
    )
    return result.get("result", {})
