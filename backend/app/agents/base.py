"""
Shared base logic for research agents.
Each agent: receives a scoped focus question, runs tools, builds AgentFinding.

Tool resolution order:
  1. MCP-backed LangChain tool (preferred — richer metadata, standardised interface)
  2. Direct SDK wrapper from tools/implementations/ (fallback when MCP server unavailable)
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import BaseTool
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.config import get_settings
from app.agents.schemas import AgentFinding, Finding, Evidence
from app.tools.confidence import calculate_confidence
from app.tools.base import ToolResult
from app.tools.mcp_client import get_mcp_tools
from app.tools.registry import get_tools_for

settings = get_settings()


def get_llm(temperature: float | None = None):
    t = temperature if temperature is not None else settings.agent_temperature
    if settings.anthropic_api_key:
        return ChatAnthropic(
            model="claude-sonnet-4-5",
            api_key=settings.anthropic_api_key,
            temperature=t,
        )
    return ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        google_api_key=settings.google_api_key,
        temperature=t,
    )


async def get_agent_tools(agent_id: str) -> tuple[list[BaseTool], dict[str, Any]]:
    """
    Returns (mcp_tools, sdk_tools) for an agent.

    - mcp_tools: LangChain BaseTool list from MCP servers (preferred, bind to LLM directly)
    - sdk_tools: {name: callable} from direct SDK wrappers (fallback)

    Agents should:
      1. Bind mcp_tools to the LLM via llm.bind_tools(mcp_tools) for tool-calling mode
      2. Use sdk_tools for programmatic calls when MCP has no server for that tool
    """
    mcp_tools = await get_mcp_tools()
    sdk_tools = get_tools_for(agent_id)

    # Remove SDK entries that have an MCP equivalent (avoid double-calling)
    mcp_tool_names = {t.name for t in mcp_tools}
    sdk_only = {k: v for k, v in sdk_tools.items() if k not in mcp_tool_names}

    return mcp_tools, sdk_only


async def build_finding_from_results(
    results: list[ToolResult],
    category: str,
    claim: str,
    tags: list[str],
    db,
) -> Finding:
    """
    Builds a typed Finding from raw ToolResults, calculating confidence per evidence item.
    """
    evidence_items = []
    for r in results:
        if r.error or not r.content:
            continue
        score, breakdown = await calculate_confidence(
            tool_name=r.tool_name,
            recency=r.recency,
            source_count=len(results),
            quote_present=bool(r.quote),
            db=db,
        )
        ev = Evidence(
            source_url=r.source_url,
            source_name=r.source_name,
            markdown_link=r.as_markdown_link(),
            quote=r.quote,
            tool_used=r.tool_name,
            retrieved_at=datetime.now(timezone.utc).isoformat(),
            recency=r.recency,
            confidence_score=score,
            confidence_breakdown=breakdown,
        )
        evidence_items.append(ev)

    if not evidence_items:
        avg_confidence = 0.0
    else:
        avg_confidence = sum(e.confidence_score for e in evidence_items) / len(evidence_items)

    strength = "strong" if avg_confidence >= 0.75 else "moderate" if avg_confidence >= 0.5 else "weak"

    return Finding(
        category=category,
        claim=claim,
        evidence=evidence_items,
        confidence=round(avg_confidence, 4),
        signal_strength=strength,
        tags=tags,
    )


def agent_finding_from_llm_json(
    agent_name: str,
    focus_question: str,
    llm_output: str,
) -> AgentFinding:
    """
    Parse LLM output (JSON string) into a typed AgentFinding.
    Falls back gracefully if parsing fails.
    """
    try:
        data = json.loads(llm_output)
        findings = [Finding(**f) for f in data.get("findings", [])]
        return AgentFinding(
            agent_name=agent_name,
            focus_question=focus_question,
            query_relevance=data.get("query_relevance", 1.0),
            confidence_overall=data.get("confidence_overall", 0.5),
            findings=findings,
            gaps=data.get("gaps", []),
            deviation_notes=data.get("deviation_notes", []),
            raw_sources_count=data.get("raw_sources_count", len(findings)),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
    except Exception:
        return AgentFinding(
            agent_name=agent_name,
            focus_question=focus_question,
            query_relevance=0.0,
            confidence_overall=0.0,
            findings=[],
            gaps=["Failed to parse agent output"],
            deviation_notes=[f"Raw output: {llm_output[:200]}"],
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
