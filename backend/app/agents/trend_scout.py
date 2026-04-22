"""Trend Scout — PESTEL analyst. Answers WHY the market is moving."""
from __future__ import annotations
import json
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage

import logging

from app.agents.base import get_llm, agent_finding_from_llm_json, coerce_llm_content, log_tool_results
from app.agents.prompts import TREND_SCOUT_PROMPT
from app.agents.schemas import AgentFinding
from app.agents.state import ResearchState
from app.tools.registry import get_tools_for

AGENT_NAME = "trend_scout"
logger = logging.getLogger(__name__)

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
    logger.info("trend_scout | START focus=%r tools_available=%s", focus[:80], list(tools.keys()))

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
    llm_text = coerce_llm_content(response.content) if hasattr(response, "content") else str(response)
    logger.info("trend_scout | llm_raw_prefix=%r", llm_text[:300])

    log_tool_results(AGENT_NAME, tool_results)
    finding = agent_finding_from_llm_json(AGENT_NAME, focus, _extract_json(llm_text))
    finding.raw_sources_count = len(tool_results)
    finding.timestamp = datetime.now(timezone.utc).isoformat()
    logger.info("trend_scout | DONE findings=%d confidence=%.2f gaps=%s",
                len(finding.findings), finding.confidence_overall, finding.gaps)
    return {"agent_findings": [finding]}


def _extract_keywords(query: str) -> list[str]:
    words = [w for w in query.split() if len(w) > 4]
    return words[:3] if words else [query[:50]]


def _extract_json(text: str) -> str:
    """Extract the outermost JSON object from LLM text.

    Handles:
    - <think>...</think> chain-of-thought blocks (qwen3 / llama reasoning models)
    - JSON placed INSIDE the think block (reasoning model answered in reasoning)
    - Unclosed <think> tags (token limit hit mid-reasoning — JSON truncated)
    - Markdown code fences (```json ... ```)
    - Truncated JSON (brace-balanced extraction, falls back gracefully)
    """
    import re
    import json as _json
    import logging as _log

    _logger = _log.getLogger("app.agents._extract_json")

    def _clean(s: str) -> str:
        """Strip code fences."""
        s = re.sub(r"```(?:json)?\s*", "", s).replace("```", "").strip()
        return s

    def _brace_extract(s: str) -> str | None:
        """
        Find the first '{' then walk forward balancing braces.
        Returns the longest valid JSON object starting at that '{'.
        Falls back to a greedy regex slice if brace-walking produces invalid JSON.
        """
        start = s.find("{")
        if start == -1:
            return None
        depth = 0
        in_str = False
        escape = False
        for i, ch in enumerate(s[start:], start):
            if escape:
                escape = False
                continue
            if ch == "\\" and in_str:
                escape = True
                continue
            if ch == '"':
                in_str = not in_str
                continue
            if in_str:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = s[start : i + 1]
                    try:
                        _json.loads(candidate)
                        return candidate
                    except _json.JSONDecodeError:
                        # Try to return it anyway — caller will handle
                        return candidate
        # Brace never closed (truncated output) — return from start to end
        # The caller's json.loads will fail gracefully; log for diagnosis
        fragment = s[start:]
        _logger.warning("_extract_json: unclosed JSON (truncated output), fragment len=%d", len(fragment))
        return fragment if fragment else None

    def _find_in(s: str) -> str | None:
        s = _clean(s)
        return _brace_extract(s)

    # Priority 1: text OUTSIDE <think> blocks
    outside = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE).strip()
    result = _find_in(outside)
    if result:
        return result

    # Priority 2: text INSIDE <think> blocks (reasoning model answered in thinking)
    think_match = re.search(r"<think>([\s\S]*?)</think>", text, flags=re.IGNORECASE)
    if think_match:
        result = _find_in(think_match.group(1))
        if result:
            _logger.debug("_extract_json: JSON found inside <think> block")
            return result

    # Priority 3: full text (unclosed <think> — no </think> present)
    result = _find_in(text)
    if result:
        _logger.debug("_extract_json: JSON found in full text (fallback, likely unclosed think block)")
        return result

    _logger.warning("_extract_json: no JSON found — raw prefix: %r", text[:300])
    return "{}"
