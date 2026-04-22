"""
Synthesis Node — 3-phase LLM reasoning.
Phase 1: relevance audit. Phase 2: gap check. Phase 3: merge & decide routing.
"""
from __future__ import annotations
import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base import get_llm, coerce_llm_content
from app.agents.prompts import SYNTHESIS_PROMPT
from app.agents.schemas import SynthesisResult, Finding, Evidence, ContentBrief
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
        [f.model_dump() for f in state.get("agent_findings", [])],
        indent=2,
        default=str,
    )[:10000]

    prompt = SYNTHESIS_PROMPT.format(
        user_query=state["user_query"],
        agent_findings_json=findings_json,
    )
    schema_hint = """
Return JSON:
{
  "query_answered": true,
  "coverage_score": 0.85,
  "key_findings": [<Finding objects>],
  "contradictions": ["..."],
  "gaps": ["..."],
  "flagged_deviations": ["..."],
  "agent_confidence_map": {"trend_scout": 0.8, ...},
  "ready_for_content": false
}
"""
    response = await llm.ainvoke([
        SystemMessage(content=prompt + schema_hint),
        HumanMessage(content=f"Synthesise findings for: {state['user_query']}"),
    ])
    llm_text = coerce_llm_content(response.content) if hasattr(response, "content") else str(response)
    synthesis = _parse_synthesis(llm_text)

    routing = "to_content_agent" if synthesis.ready_for_content else "to_user"
    logger.info("synthesis | DONE query_answered=%s coverage=%.2f key_findings=%d routing=%s gaps=%s",
                synthesis.query_answered, synthesis.coverage_score,
                len(synthesis.key_findings), routing, synthesis.gaps)

    result: dict = {"synthesis_result": synthesis, "routing": routing}

    # When routing to content agent, populate ContentBrief so the content graph
    # has all research findings — without this the content strategist runs blind.
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


def _parse_synthesis(text: str) -> SynthesisResult:
    import re
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return SynthesisResult(
            query_answered=False,
            coverage_score=0.0,
            gaps=["Synthesis failed to produce structured output"],
        )
    try:
        data = json.loads(match.group(0))
        raw_findings = data.get("key_findings", [])
        findings = []
        for f in raw_findings:
            evidence = [Evidence(**e) for e in f.get("evidence", [])]
            findings.append(Finding(
                category=f.get("category", "General"),
                claim=f.get("claim", ""),
                evidence=evidence,
                confidence=f.get("confidence", 0.5),
                signal_strength=f.get("signal_strength", "moderate"),
                tags=f.get("tags", []),
            ))
        return SynthesisResult(
            query_answered=data.get("query_answered", False),
            coverage_score=data.get("coverage_score", 0.0),
            key_findings=findings,
            contradictions=data.get("contradictions", []),
            gaps=data.get("gaps", []),
            flagged_deviations=data.get("flagged_deviations", []),
            agent_confidence_map=data.get("agent_confidence_map", {}),
            ready_for_content=data.get("ready_for_content", False),
        )
    except Exception:
        return SynthesisResult(query_answered=False, gaps=["Failed to parse synthesis output"])
