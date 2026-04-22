"""
Synthesis Node — 3-phase LLM reasoning + user report in a single LLM call.
Replaces the old synthesis_node + summarizer_node two-pass approach.
"""
from __future__ import annotations
import json
import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base import get_llm, coerce_llm_content, llm_ainvoke_with_retry
from app.agents.prompts import SYNTHESIS_PROMPT
from app.agents.schemas import SynthesisResult, Finding, Evidence, ContentBrief, UserReport, SourceLink
from app.agents.state import ResearchState

logger = logging.getLogger(__name__)


async def synthesis_node(state: ResearchState) -> dict:
    findings_in = state.get("agent_findings", [])
    logger.info("synthesis | START agent_findings=%d", len(findings_in))
    for f in findings_in:
        agent = getattr(f, "agent_name", "?")
        conf = getattr(f, "confidence_overall", 0)
        n_findings = len(getattr(f, "findings", []))
        gaps = getattr(f, "gaps", [])
        logger.info("synthesis | AGENT %-20s confidence=%.2f findings=%d gaps=%s",
                    agent, conf, n_findings, gaps)

    llm = get_llm(temperature=0.1)

    findings_json = json.dumps(
        [f.model_dump() for f in findings_in],
        indent=2,
        default=str,
    )[:6000]

    prompt = SYNTHESIS_PROMPT.format(
        user_query=state["user_query"],
        agent_findings_json=findings_json,
    )

    response = await llm_ainvoke_with_retry(llm, [
        SystemMessage(content=prompt),
        HumanMessage(content=f"Synthesise and report on: {state['user_query']}"),
    ])
    llm_text = coerce_llm_content(response.content) if hasattr(response, "content") else str(response)

    synthesis, user_report = _parse_combined(llm_text)

    routing = "to_content_agent" if synthesis.ready_for_content else "to_user"
    logger.info(
        "synthesis | DONE query_answered=%s coverage=%.2f key_findings=%d routing=%s gaps=%s",
        synthesis.query_answered, synthesis.coverage_score,
        len(synthesis.key_findings), routing, synthesis.gaps,
    )

    result: dict = {
        "synthesis_result": synthesis,
        "user_report": user_report,
        "routing": routing,
    }

    if routing == "to_content_agent":
        content_brief = ContentBrief(
            synthesis=synthesis,
            workspace_context=state.get("workspace_context", {}),
            temporal_context=None,
        )
        result["content_brief"] = content_brief
        logger.info("synthesis | ContentBrief written findings=%d coverage=%.2f",
                    len(synthesis.key_findings), synthesis.coverage_score)

    return result


def _parse_combined(text: str) -> tuple[SynthesisResult, UserReport]:
    """Parse one JSON blob into both SynthesisResult and UserReport."""
    # Strip <think> blocks (reasoning models)
    text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"```(?:json)?\s*", "", text).replace("```", "").strip()

    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        logger.warning("synthesis: no JSON found in output, raw prefix: %r", text[:200])
        empty_synthesis = SynthesisResult(
            query_answered=False,
            coverage_score=0.0,
            gaps=["Synthesis produced no structured output"],
        )
        empty_report = UserReport(
            summary="Research complete but synthesis failed to produce a structured output.",
            key_insights=[],
            gaps=["Synthesis error"],
            confidence=0.0,
            sources=[],
        )
        return empty_synthesis, empty_report

    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        logger.warning("synthesis: JSON parse error — %s, raw prefix: %r", exc, text[:200])
        empty_synthesis = SynthesisResult(query_answered=False, gaps=["Failed to parse synthesis output"])
        empty_report = UserReport(
            summary=text[:500] if text else "Research complete.",
            key_insights=[],
            gaps=["Parse error"],
            confidence=0.0,
            sources=[],
        )
        return empty_synthesis, empty_report

    # --- Build SynthesisResult ---
    raw_findings = data.get("key_findings", [])
    findings = []
    for f in raw_findings:
        evidence = []
        for e in f.get("evidence", []):
            try:
                evidence.append(Evidence(**e))
            except Exception:
                pass
        findings.append(Finding(
            category=f.get("category", "General"),
            claim=f.get("claim", ""),
            evidence=evidence,
            confidence=f.get("confidence", 0.5),
            signal_strength=f.get("signal_strength", "moderate"),
            tags=f.get("tags", []),
        ))

    synthesis = SynthesisResult(
        query_answered=data.get("query_answered", False),
        coverage_score=data.get("coverage_score", 0.0),
        key_findings=findings,
        contradictions=data.get("contradictions", []),
        gaps=data.get("gaps", []),
        flagged_deviations=data.get("flagged_deviations", []),
        agent_confidence_map=data.get("agent_confidence_map", {}),
        ready_for_content=data.get("ready_for_content", False),
    )

    # --- Build UserReport ---
    # Pre-extract sources from key_findings evidence as fallback
    seen_urls: set[str] = set()
    extracted_sources: list[SourceLink] = []
    for finding in findings:
        for ev in finding.evidence:
            url = getattr(ev, "source_url", None)
            name = getattr(ev, "source_name", None)
            if url and url not in seen_urls:
                seen_urls.add(url)
                extracted_sources.append(SourceLink(name=name or url, url=url))

    # Merge LLM-provided sources with pre-extracted ones
    llm_sources = []
    for s in data.get("sources", []):
        url = s.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            llm_sources.append(SourceLink(name=s.get("name", url), url=url))
    all_sources = llm_sources + extracted_sources

    user_report = UserReport(
        summary=data.get("summary", "Research complete."),
        key_insights=data.get("key_insights", [])[:7],
        gaps=data.get("gaps", []),
        confidence=float(data.get("confidence", data.get("coverage_score", 0.0))),
        sources=all_sources,
        query_answered=data.get("query_answered", True),
    )

    return synthesis, user_report

