"""
Synthesis Node — 3-phase LLM reasoning.
Phase 1: relevance audit. Phase 2: gap check. Phase 3: merge & decide routing.
"""
from __future__ import annotations
import json

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base import get_llm
from app.agents.prompts import SYNTHESIS_PROMPT
from app.agents.schemas import SynthesisResult, Finding, Evidence
from app.agents.state import ResearchState


async def synthesis_node(state: ResearchState) -> dict:
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
    llm_text = response.content if hasattr(response, "content") else str(response)
    synthesis = _parse_synthesis(llm_text)

    routing = "to_content_agent" if synthesis.ready_for_content else "to_user"
    return {"synthesis_result": synthesis, "routing": routing}


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
