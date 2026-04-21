"""Contextual Scout — cross-domain analyst. Answers WHAT is coming from outside the frame."""
from __future__ import annotations
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base import get_llm, agent_finding_from_llm_json
from app.agents.prompts import CONTEXTUAL_SCOUT_PROMPT
from app.agents.state import ResearchState
from app.tools.registry import get_tools_for

AGENT_NAME = "contextual_scout"


async def contextual_scout_node(state: ResearchState, db=None) -> dict:
    focus = state.get("focus", state["user_query"])
    tools = get_tools_for(AGENT_NAME)
    llm = get_llm()

    tool_results = []

    if "exa_search" in tools:
        results = await tools["exa_search"](f"{focus} adjacent technology disruption emerging", num_results=5)
        tool_results.extend(results)

    if "crunchbase_search" in tools:
        results = await tools["crunchbase_search"](focus, limit=8)
        tool_results.extend(results)

    if "patent_search" in tools:
        results = await tools["patent_search"](focus, limit=5)
        tool_results.extend(results)

    if "hn_search" in tools:
        results = await tools["hn_search"](focus, tags="story", hits_per_page=10)
        tool_results.extend(results)

    if "tavily_search" in tools:
        results = await tools["tavily_search"](f"{focus} disruption adjacent market 2025 2026", max_results=5)
        tool_results.extend(results)

    tool_context = "\n\n".join(
        f"[{r.tool_name}] {r.source_name or ''}\nURL: {r.source_url or 'N/A'}\n{r.content[:600]}"
        for r in tool_results if not r.error and r.content
    )

    system = CONTEXTUAL_SCOUT_PROMPT.format(focus=focus)
    synthesis_prompt = (
        f"Based on the following cross-domain intelligence, produce your findings as JSON "
        f"(same schema as briefed). Be explicit about signal confidence — patent = weak, "
        f"multiple confirming signals = strong.\n\n"
        f"FOCUS: {focus}\n\nDATA:\n{tool_context[:8000]}"
    )
    response = await llm.ainvoke([SystemMessage(content=system), HumanMessage(content=synthesis_prompt)])
    llm_text = response.content if hasattr(response, "content") else str(response)

    from app.agents.trend_scout import _extract_json
    finding = agent_finding_from_llm_json(AGENT_NAME, focus, _extract_json(llm_text))
    finding.raw_sources_count = len(tool_results)
    finding.timestamp = datetime.now(timezone.utc).isoformat()

    return {"agent_findings": [finding]}
