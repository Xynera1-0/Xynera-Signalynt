"""Spy Scout — competitive intelligence. Answers WHAT competitors are doing."""
from __future__ import annotations
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage

import logging

from app.agents.base import get_llm, agent_finding_from_llm_json, coerce_llm_content, log_tool_results, llm_ainvoke_with_retry
from app.agents.prompts import SPY_SCOUT_PROMPT
from app.agents.state import ResearchState
from app.tools.registry import get_tools_for

AGENT_NAME = "spy_scout"
logger = logging.getLogger(__name__)

SPY_SCOUT_SCHEMA_INSTRUCTIONS = """
After gathering competitive intelligence, return ONLY a JSON object — no markdown, no prose, no code fences:
{
  "findings": [
    {
      "claim": "single falsifiable competitive insight",
      "evidence": [{"source_url": "...", "source_name": "...", "quote": "...", "tool_used": "...", "retrieved_at": "...", "recency": "7d", "confidence_score": 0.8}],
      "confidence": 0.8,
      "signal_strength": "strong|moderate|weak",
      "tags": ["ad_strategy", "positioning", "creative"]
    }
  ],
  "gaps": ["what competitor data couldn't be accessed"],
  "deviation_notes": [],
  "query_relevance": 0.95,
  "confidence_overall": 0.75,
  "raw_sources_count": 10
}
"""


async def spy_scout_node(state: ResearchState, db=None) -> dict:
    focus = state.get("focus", state["user_query"])
    tools = get_tools_for(AGENT_NAME)
    llm = get_llm()
    logger.info("spy_scout | START focus=%r tools_available=%s", focus[:80], list(tools.keys()))

    tool_results = []

    # ── Phase 1: Discover who the competitors actually are ───────────────────
    # Search for "{topic} brands/manufacturers/companies" to get named competitors
    # before trying to analyse them.
    competitor_names: list[str] = []
    competitor_domains: list[str] = []

    if "tavily_search" in tools:
        discovery_queries = [
            f"{focus} brands manufacturers companies market",
            f"{focus} top competitors market leaders",
        ]
        for dq in discovery_queries:
            results = await tools["tavily_search"](dq, max_results=5)
            tool_results.extend(results)
        # Extract any brand/domain mentions from the content
        import re
        discovery_text = " ".join(
            r.content for r in tool_results if not r.error and r.content
        )
        # Pull domains found in source URLs and content
        found_domains = re.findall(
            r'(?:https?://)?(?:www\.)?([a-zA-Z0-9-]+\.(?:com|lk|io|co|net|org|ai))',
            discovery_text,
        )
        # Exclude known research/news domains
        _EXCLUDE = {"tavily", "exa", "algolia", "wikipedia", "google", "facebook",
                    "linkedin", "twitter", "instagram", "youtube", "amazon"}
        competitor_domains = list(dict.fromkeys(
            d for d in found_domains if d.split(".")[0].lower() not in _EXCLUDE
        ))[:5]
        logger.info("spy_scout | Phase1 discovery domains=%s", competitor_domains)

    # ── Phase 2: Scrape competitor pages + get ad/backlink intel ─────────────
    if "exa_search" in tools:
        results = await tools["exa_search"](f"{focus} competitor marketing strategy positioning", num_results=5)
        tool_results.extend(results)

    if "tavily_search" in tools:
        results = await tools["tavily_search"](f"{focus} competitor ad campaign strategy 2025 2026", max_results=5)
        tool_results.extend(results)

    if "meta_ad_search" in tools:
        results = await tools["meta_ad_search"](focus, limit=10)
        tool_results.extend(results)

    if "linkedin_ad_search" in tools:
        results = await tools["linkedin_ad_search"](focus, limit=10)
        tool_results.extend(results)

    # ── Phase 3: Moz DA / backlink analysis on discovered competitor domains ──
    if "moz_domain_metrics" in tools and competitor_domains:
        for dom in competitor_domains[:3]:
            results = await tools["moz_domain_metrics"](dom)
            tool_results.extend(results)
            logger.info("spy_scout | Moz query domain=%s results=%d", dom, len(results))

    tool_context = "\n\n".join(
        f"[{r.tool_name}] {r.source_name or ''}\nURL: {r.source_url or 'N/A'}\n{r.content[:250]}"
        for r in tool_results if not r.error and r.content
    )

    system = SPY_SCOUT_PROMPT.format(focus=focus) + "\n\n" + SPY_SCOUT_SCHEMA_INSTRUCTIONS
    synthesis_prompt = (
        f"Based on the following competitive intelligence data, return ONLY a JSON object "
        f"matching the schema in your instructions. No markdown, no explanation.\n\n"
        f"FOCUS: {focus}\n\nDATA:\n{tool_context[:4000]}"
    )
    response = await llm_ainvoke_with_retry(llm, [SystemMessage(content=system), HumanMessage(content=synthesis_prompt)])
    llm_text = coerce_llm_content(response.content) if hasattr(response, "content") else str(response)
    logger.info("spy_scout | llm_raw_prefix=%r", llm_text[:300])

    from app.agents.trend_scout import _extract_json
    log_tool_results(AGENT_NAME, tool_results)
    finding = agent_finding_from_llm_json(AGENT_NAME, focus, _extract_json(llm_text))
    finding.raw_sources_count = len(tool_results)
    finding.timestamp = datetime.now(timezone.utc).isoformat()
    logger.info("spy_scout | DONE findings=%d confidence=%.2f gaps=%s",
                len(finding.findings), finding.confidence_overall, finding.gaps)
    return {"agent_findings": [finding]}
