"""
Summarizer — final LLM node for user-facing output.
Reached only when routing == "to_user".
Builds UserReport with sources as [name](url) links.
"""
from __future__ import annotations
import json
import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base import get_llm, coerce_llm_content
from app.agents.prompts import SUMMARIZER_PROMPT
from app.agents.schemas import UserReport, SourceLink
from app.agents.state import ResearchState

logger = logging.getLogger(__name__)


async def summarizer_node(state: ResearchState) -> dict:
    llm = get_llm(temperature=0.2)
    synthesis = state.get("synthesis_result")
    if synthesis is None:
        return {"user_report": UserReport(
            summary="No synthesis available.",
            key_insights=[],
            gaps=["No findings were synthesised"],
            confidence=0.0,
            sources=[],
        )}

    synthesis_json = json.dumps(synthesis.model_dump(), indent=2, default=str)[:8000]

    # Pre-extract all source URLs from findings evidence so the LLM doesn't miss them
    seen_urls: set[str] = set()
    extracted_sources: list[dict] = []
    for finding in (synthesis.key_findings or []):
        for ev in (finding.evidence or []):
            url = getattr(ev, "source_url", None) or (ev.get("source_url") if isinstance(ev, dict) else None)
            name = getattr(ev, "source_name", None) or (ev.get("source_name") if isinstance(ev, dict) else None)
            if url and url not in seen_urls:
                seen_urls.add(url)
                extracted_sources.append({"name": name or url, "url": url})

    sources_hint = ""
    if extracted_sources:
        sources_hint = (
            "\n\nKnown sources from findings (include ALL of these in the sources array):\n"
            + json.dumps(extracted_sources, indent=2)
        )

    prompt = SUMMARIZER_PROMPT.format(
        user_query=state["user_query"],
        synthesis_json=synthesis_json + sources_hint,
    )

    # Use JSON mode when the provider supports it (Groq / OpenAI compatible)
    try:
        json_llm = llm.bind(response_format={"type": "json_object"})
        response = await json_llm.ainvoke([
            SystemMessage(content=prompt),
            HumanMessage(content=state["user_query"]),
        ])
    except Exception:
        # Fallback: plain invocation without JSON mode
        response = await llm.ainvoke([
            SystemMessage(content=prompt),
            HumanMessage(content=state["user_query"]),
        ])

    llm_text = coerce_llm_content(response.content) if hasattr(response, "content") else str(response)
    logger.debug("summarizer raw output: %s", llm_text[:500])
    report = _parse_report(llm_text, fallback_query=state["user_query"])
    logger.info("summarizer | DONE summary_len=%d insights=%d gaps=%d sources=%d confidence=%.2f",
                len(report.summary), len(report.key_insights),
                len(report.gaps), len(report.sources), report.confidence)
    return {"user_report": report}


def _parse_report(text: str, fallback_query: str = "") -> UserReport:
    # Strip <think>...</think> chain-of-thought (Groq llama models)
    text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE).strip()
    # Strip markdown code fences if model added them despite instructions
    text = re.sub(r"```(?:json)?\s*", "", text).strip()

    # Extract the outermost JSON object
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        logger.warning("summarizer: no JSON object found in output")
        return UserReport(
            summary=text if text else "Research complete — no structured output produced.",
            key_insights=[],
            gaps=["Could not extract structured report from summarizer"],
            confidence=0.0,
            sources=[],
        )
    try:
        data = json.loads(match.group(0))
        sources = [
            SourceLink(name=s.get("name", "Source"), url=s["url"])
            for s in data.get("sources", [])
            if s.get("url")
        ]
        return UserReport(
            summary=data.get("summary", ""),
            key_insights=data.get("key_insights", [])[:7],
            gaps=data.get("gaps", []),
            confidence=float(data.get("confidence", data.get("overall_confidence", 0.0))),
            sources=sources,
            query_answered=data.get("query_answered", True),
        )
    except Exception as exc:
        logger.warning("summarizer: JSON parse failed — %s", exc)
        # Return the full raw text as summary rather than truncating it
        return UserReport(
            summary=text,
            key_insights=[],
            gaps=["Failed to parse structured report"],
            confidence=0.0,
            sources=[],
        )
