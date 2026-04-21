"""Trend Scout — PESTEL analyst. Answers WHY the market is moving."""
from __future__ import annotations
import json
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base import get_llm, agent_finding_from_llm_json
from app.agents.prompts import TREND_SCOUT_PROMPT
from app.agents.schemas import AgentFinding
from app.agents.state import ResearchState
from app.tools.registry import get_tools_for

AGENT_NAME = "trend_scout"

TOOL_SCHEMA_INSTRUCTIONS = """
You have these tools available. Call them by including a JSON block:
{"tool": "<tool_name>", "args": {...}}

Tools: tavily_search(query, max_results=5), exa_search(query, num_results=5),
firecrawl_scrape(url), serpapi_search(query, engine='google', num=10),
pytrends_interest(keywords=['...'], timeframe='today 3-m', geo=''),
newsapi_headlines(query, days_back=7), semrush_keyword_overview(keyword)

After gathering evidence, return your findings as JSON:
{
  "findings": [
    {
      "category": "Political|Economic|Social|Technological|Environmental|Legal",
      "claim": "single falsifiable statement",
      "evidence": [{"source_url": "...", "source_name": "...", "quote": "...", "tool_used": "...", "retrieved_at": "...", "recency": "7d", "confidence_score": 0.8, "confidence_breakdown": {}}],
      "confidence": 0.8,
      "signal_strength": "strong|moderate|weak",
      "tags": ["..."]
    }
  ],
  "gaps": ["what couldn't be found"],
  "deviation_notes": [],
  "query_relevance": 0.95,
  "confidence_overall": 0.78,
  "raw_sources_count": 12
}
"""


async def trend_scout_node(state: ResearchState, db=None) -> dict:
    focus = state.get("focus", state["user_query"])
    tools = get_tools_for(AGENT_NAME)
    llm = get_llm()

    system = TREND_SCOUT_PROMPT.format(focus=focus) + "\n\n" + TOOL_SCHEMA_INSTRUCTIONS
    messages = [SystemMessage(content=system), HumanMessage(content=f"Research query: {focus}")]

    tool_results = []

    # Gather data via tools
    if "tavily_search" in tools:
        results = await tools["tavily_search"](focus, max_results=5)
        tool_results.extend(results)

    if "exa_search" in tools:
        results = await tools["exa_search"](focus, num_results=5)
        tool_results.extend(results)

    if "newsapi_headlines" in tools:
        results = await tools["newsapi_headlines"](focus, days_back=7)
        tool_results.extend(results)

    if "pytrends_interest" in tools:
        keywords = _extract_keywords(focus)
        results = await tools["pytrends_interest"](keywords)
        tool_results.extend(results)

    # Compile tool results into context for LLM
    tool_context = "\n\n".join(
        f"[{r.tool_name}] {r.source_name or ''}\nURL: {r.source_url or 'N/A'}\n{r.content[:600]}"
        for r in tool_results if not r.error and r.content
    )

    synthesis_prompt = (
        f"Based on the following research data, produce your findings as JSON.\n\n"
        f"FOCUS QUESTION: {focus}\n\nDATA:\n{tool_context[:8000]}"
    )
    response = await llm.ainvoke([SystemMessage(content=system), HumanMessage(content=synthesis_prompt)])
    llm_text = response.content if hasattr(response, "content") else str(response)

    finding = agent_finding_from_llm_json(AGENT_NAME, focus, _extract_json(llm_text))
    finding.raw_sources_count = len(tool_results)
    finding.timestamp = datetime.now(timezone.utc).isoformat()

    return {"agent_findings": [finding]}


def _extract_keywords(query: str) -> list[str]:
    words = [w for w in query.split() if len(w) > 4]
    return words[:3] if words else [query[:50]]


def _extract_json(text: str) -> str:
    import re
    match = re.search(r"\{[\s\S]*\}", text)
    return match.group(0) if match else "{}"
