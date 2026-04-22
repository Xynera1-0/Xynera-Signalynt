"""Anthropologist — sentiment specialist. Answers HOW the audience feels."""
from __future__ import annotations
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage

import logging

from app.agents.base import get_llm, agent_finding_from_llm_json, coerce_llm_content, log_tool_results, llm_ainvoke_with_retry
from app.agents.prompts import ANTHROPOLOGIST_PROMPT
from app.agents.state import ResearchState
from app.tools.registry import get_tools_for

AGENT_NAME = "anthropologist"
logger = logging.getLogger(__name__)


async def anthropologist_node(state: ResearchState, db=None) -> dict:
    focus = state.get("focus", state["user_query"])
    tools = get_tools_for(AGENT_NAME)
    llm = get_llm()
    logger.info("anthropologist | START focus=%r tools_available=%s", focus[:80], list(tools.keys()))

    tool_results = []

    if "reddit_search" in tools:
        results = await tools["reddit_search"](focus, limit=20)
        tool_results.extend(results)

    if "youtube_search" in tools:
        results = await tools["youtube_search"](focus, max_results=8)
        tool_results.extend(results)
        # Get comments from top video if found
        if results and not results[0].error:
            video_url = results[0].source_url or ""
            video_id = video_url.split("v=")[-1] if "v=" in video_url else ""
            if video_id and "youtube_comments" in tools:
                comments = await tools["youtube_comments"](video_id, max_results=30)
                tool_results.extend(comments)

    if "hn_search" in tools:
        results = await tools["hn_search"](focus, tags="comment", hits_per_page=10)
        tool_results.extend(results)

    if "exa_search" in tools:
        results = await tools["exa_search"](f"{focus} community discussion forum", num_results=5)
        tool_results.extend(results)

    tool_context = "\n\n".join(
        f"[{r.tool_name}] {r.source_name or ''}\nURL: {r.source_url or 'N/A'}\n{r.content[:300]}"
        for r in tool_results if not r.error and r.content
    )

    system = ANTHROPOLOGIST_PROMPT.format(focus=focus)
    synthesis_prompt = (
        f"Based on the following community and sentiment data, produce your findings as JSON "
        f"(same schema as briefed). Prioritise verbatim quotes as evidence.\n\n"
        f"FOCUS: {focus}\n\nDATA:\n{tool_context[:4000]}"
    )
    response = await llm_ainvoke_with_retry(llm, [SystemMessage(content=system), HumanMessage(content=synthesis_prompt)])
    llm_text = coerce_llm_content(response.content) if hasattr(response, "content") else str(response)
    logger.info("anthropologist | llm_raw_prefix=%r", llm_text[:300])

    from app.agents.trend_scout import _extract_json
    log_tool_results(AGENT_NAME, tool_results)
    finding = agent_finding_from_llm_json(AGENT_NAME, focus, _extract_json(llm_text))
    finding.raw_sources_count = len(tool_results)
    finding.timestamp = datetime.now(timezone.utc).isoformat()
    logger.info("anthropologist | DONE findings=%d confidence=%.2f gaps=%s",
                len(finding.findings), finding.confidence_overall, finding.gaps)
    return {"agent_findings": [finding]}
