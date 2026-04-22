"""
Shared base logic for research agents.
Each agent: receives a scoped focus question, runs tools, builds AgentFinding.

Tool resolution order:
  1. MCP-backed LangChain tool (preferred — richer metadata, standardised interface)
  2. Direct SDK wrapper from tools/implementations/ (fallback when MCP server unavailable)
"""
from __future__ import annotations
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Force-load .env into os.environ before anything else reads it.
# override=True ensures this wins even if pydantic-settings read .env first.
load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=True)

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import BaseTool

from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq

from app.core.config import get_settings
from app.agents.schemas import AgentFinding, Finding, Evidence
from app.tools.confidence import calculate_confidence
from app.tools.base import ToolResult
from app.tools.mcp_client import get_mcp_tools
from app.tools.registry import get_tools_for

# Do NOT cache settings at module level — get_llm() calls get_settings() fresh
# so the lru_cache is busted after load_dotenv runs above.
get_settings.cache_clear()

_RATE_LIMIT_MARKERS = (
    "429",
    "quota",
    "rate limit",
    "too many requests",
    "resource exhausted",
    "resource_exhausted",
)


def _is_rate_limit(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(m in msg for m in _RATE_LIMIT_MARKERS)


class _GrokFallback:
    """Wraps a primary LangChain chat model with a Grok fallback on rate-limit errors."""

    def __init__(self, primary, fallback):
        self._primary = primary
        self._fallback = fallback

    def invoke(self, messages, **kwargs):
        try:
            return self._primary.invoke(messages, **kwargs)
        except Exception as exc:
            if _is_rate_limit(exc):
                logging.warning("LLM rate-limit hit, switching to Grok. Error: %s", exc)
                return self._fallback.invoke(messages, **kwargs)
            raise

    async def ainvoke(self, messages, **kwargs):
        try:
            return await self._primary.ainvoke(messages, **kwargs)
        except Exception as exc:
            if _is_rate_limit(exc):
                logging.warning("LLM rate-limit hit, switching to Grok. Error: %s", exc)
                return await self._fallback.ainvoke(messages, **kwargs)
            raise

    def bind_tools(self, tools, **kwargs):
        return _GrokFallback(
            self._primary.bind_tools(tools, **kwargs),
            self._fallback.bind_tools(tools, **kwargs),
        )

    def __getattr__(self, name):
        return getattr(self._primary, name)


def coerce_llm_content(content) -> str:
    """Normalise LLM response.content to a plain string.

    Gemini (langchain_google_genai) can return a list of content-block dicts
    instead of a bare string.  This extracts text from every block so the rest
    of the codebase always gets a str.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                parts.append(block.get("text") or block.get("content") or str(block))
            else:
                parts.append(str(block))
        return " ".join(parts)
    return str(content) if content is not None else ""


def get_llm(temperature: float | None = None):
    # Read keys from os.environ first (populated by main.py's load_dotenv)
    # Fall back to settings in case os.environ somehow wasn't populated
    s = get_settings()
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY") or s.anthropic_api_key
    groq_key = os.environ.get("GROQ_API_KEY") or s.groq_api_key
    t = temperature if temperature is not None else s.agent_temperature
    
    if anthropic_key:
        return ChatAnthropic(  # type: ignore[call-arg]
            model="claude-sonnet-4-5",
            api_key=anthropic_key,
            temperature=t,
        )
    if groq_key:
        logging.info("get_llm: using Groq (groq/compound)")
        return ChatGroq(
            model="groq/compound",
            api_key=groq_key,
            temperature=t,
        )
    logging.warning("get_llm: falling back to Gemini — GROQ_API_KEY not in os.environ or settings")
    return ChatGoogleGenerativeAI(
        model="gemini-3-flash-preview",
        google_api_key=s.google_api_key,
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
    except Exception as exc:
        logging.getLogger(f"app.agents.{agent_name}").warning(
            "%s | parse_fail exc=%s raw_output=%r",
            agent_name, exc, llm_output[:400],
        )
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


def log_tool_results(agent_name: str, tool_results: list) -> None:
    """Structured log of every tool call result for an agent run."""
    _log = logging.getLogger(f"app.agents.{agent_name}")
    succeeded = [r for r in tool_results if not r.error and r.content]
    failed = [r for r in tool_results if r.error]
    _log.info(
        "%s | TOOLS called=%d succeeded=%d failed=%d",
        agent_name, len(tool_results), len(succeeded), len(failed),
    )
    for r in succeeded:
        _log.info(
            "%s | TOOL_OK  tool=%-25s source=%s chars=%d",
            agent_name, r.tool_name, (r.source_name or r.source_url or "")[:60], len(r.content),
        )
    for r in failed:
        _log.warning(
            "%s | TOOL_ERR tool=%-25s error=%s",
            agent_name, r.tool_name, str(r.error)[:120],
        )
