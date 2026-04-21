"""
Summarizer — final LLM node for user-facing output.
Reached only when routing == "to_user".
Builds UserReport with sources as [name](url) links.
"""
from __future__ import annotations
import json

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base import get_llm
from app.agents.prompts import SUMMARIZER_PROMPT
from app.agents.schemas import UserReport, SourceLink
from app.agents.state import ResearchState


async def summarizer_node(state: ResearchState) -> dict:
    llm = get_llm(temperature=0.2)
    synthesis = state.get("synthesis_result")
    if synthesis is None:
        return {"user_report": UserReport(
            summary="No synthesis available.",
            key_insights=[],
            gaps=["No findings were synthesised"],
            overall_confidence=0.0,
            sources=[],
        )}

    synthesis_json = json.dumps(synthesis.model_dump(), indent=2, default=str)[:8000]

    prompt = SUMMARIZER_PROMPT.format(
        user_query=state["user_query"],
        synthesis_json=synthesis_json,
    )
    schema_hint = """
Return JSON:
{
  "summary": "3-5 sentence answer",
  "key_insights": ["insight 1", ...],
  "gaps": ["what could not be found"],
  "overall_confidence": 0.75,
  "sources": [{"name": "Source Name", "url": "https://..."}]
}
Maximum 7 key_insights. Every source in key_insights must appear in the sources list.
"""
    response = await llm.ainvoke([
        SystemMessage(content=prompt + schema_hint),
        HumanMessage(content=f"Summarise for user: {state['user_query']}"),
    ])
    llm_text = response.content if hasattr(response, "content") else str(response)
    report = _parse_report(llm_text)

    return {"user_report": report}


def _parse_report(text: str) -> UserReport:
    import re
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return UserReport(
            summary=text[:500],
            key_insights=[],
            gaps=["Could not extract structured report"],
            overall_confidence=0.0,
            sources=[],
        )
    try:
        data = json.loads(match.group(0))
        sources = [
            SourceLink(name=s["name"], url=s["url"])
            for s in data.get("sources", [])
            if s.get("url")
        ]
        return UserReport(
            summary=data.get("summary", ""),
            key_insights=data.get("key_insights", [])[:7],
            gaps=data.get("gaps", []),
            overall_confidence=data.get("overall_confidence", 0.0),
            sources=sources,
        )
    except Exception:
        return UserReport(
            summary=text[:500],
            key_insights=[],
            gaps=["Failed to parse summarizer output"],
            overall_confidence=0.0,
            sources=[],
        )
