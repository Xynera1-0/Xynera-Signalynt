"""
Top-Level Supervisor Graph — routes across all three teams.
Planner node reads Neo4j KB before deciding team sequence.

LangGraph best practices:
  - TypedDict state (NOT Pydantic BaseModel as graph schema)
  - StateGraph(SupervisorState) — not StateGraph(dict)
  - Nodes return ONLY changed fields
"""
from __future__ import annotations
import json
import logging
import uuid
from typing import TypedDict, Optional

from langgraph.graph import StateGraph, END
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.agents.base import get_llm, coerce_llm_content
from app.db.kb_reader import read_relevant_kb_context

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# State
# ─────────────────────────────────────────────────────────────────────────────

class SupervisorState(TypedDict, total=False):
    # ── User input (required at invocation) ────────────────────────────
    user_query: str
    workspace_id: str
    campaign_id: str
    # ── Optional hint from the UI tool selector (may be empty/None) ───
    # Values: "research" | "generate_content" | "post_to_channel" | "full_workflow" | ""
    # The planner uses this as a bias, not a strict override.
    tool_hint: str
    # ── Set to conversation_id so LangGraph checkpoints per conversation
    thread_id: str
    # ── Last N messages from the conversation, newest last ─────────────
    # Each entry: {"role": "user"|"assistant", "content": str}
    conversation_history: list
    # ── KB context injected by Planner ──────────────────────────────
    kb_context: dict
    # ── Available content from Postgres (populated by planner) ──────
    available_campaigns: list
    # ── Planner output ────────────────────────────────────────────
    plan: dict
    route: str
    # route values:
    #   chat             — generic / conversational message, direct LLM reply
    #   research_only    — insights only, no content
    #   content_only     — user provides brief, skip research
    #   research_content — research + create content, don't post
    #   post_existing    — post a previously created campaign
    #   full_campaign    — full loop: research → content → A/B publish → analytics
    action: str         # "create" | "publish_existing"
    # ── Team outputs ─────────────────────────────────────────────
    research_result: dict
    content_result: dict
    campaign_result: dict
    # ── For the chat route: direct LLM reply text ─────────────────
    chat_reply: str
    # ── Status ────────────────────────────────────────────────
    status: str


# ─────────────────────────────────────────────────────────────────────────────
# Planner Node
# Reads KB, decides route and injects prior knowledge as context
# ─────────────────────────────────────────────────────────────────────────────

async def _fetch_available_campaigns(workspace_id: str) -> list[dict]:
    """
    Fetches the 10 most recent campaigns with their content summaries.
    Gives the planner context about what content already exists so it can
    handle "post last week's campaign" type queries.
    """
    import asyncio
    from app.db import get_db_cursor

    def _query():
        try:
            with get_db_cursor() as cursor:
                cursor.execute("""
                    SELECT
                        c.id,
                        c.name,
                        c.objective,
                        c.status,
                        c.platforms,
                        c.hypothesis,
                        c.created_at,
                        json_agg(
                            json_build_object(
                                'id',           cc.id,
                                'platform',     cc.platform,
                                'content_type', cc.content_type,
                                'headline',     cc.headline,
                                'is_base',      cc.is_base
                            )
                        ) FILTER (WHERE cc.id IS NOT NULL) AS content
                    FROM campaigns c
                    LEFT JOIN campaign_content cc ON cc.campaign_id = c.id
                    WHERE c.workspace_id = %s::uuid
                    GROUP BY c.id
                    ORDER BY c.created_at DESC
                    LIMIT 10
                """, (workspace_id,))
                rows = cursor.fetchall()
            return [
                {
                    "id": str(r["id"]),
                    "name": r["name"],
                    "objective": r["objective"],
                    "status": r["status"],
                    "platforms": r["platforms"],
                    "hypothesis": r["hypothesis"],
                    "created_at": str(r["created_at"]),
                    "content": r["content"] or [],
                }
                for r in rows
            ]
        except Exception:
            return []

    return await asyncio.to_thread(_query)


async def planner_node(state: SupervisorState) -> dict:
    user_query = state.get("user_query", "")
    workspace_id = state.get("workspace_id", "")
    logger.info("planner | workspace=%s query=%r", workspace_id, user_query[:80])

    # ── Fast-path 1: short/conversational messages never trigger campaign work ──
    _CHAT_TRIGGERS = {
        "hi", "hey", "hello", "thanks", "thank you", "ok", "okay", "sure",
        "great", "cool", "bye", "goodbye", "good morning", "good afternoon",
        "good evening", "how are you", "what can you do", "what do you do",
        "help", "who are you", "what are you",
    }
    _query_lower = user_query.strip().lower().rstrip("!?.,")
    if len(user_query.strip()) < 40 and _query_lower in _CHAT_TRIGGERS:
        logger.info("planner | fast-path chat route for short conversational message")
        return {
            "kb_context": [],
            "available_campaigns": [],
            "plan": {"route": "chat"},
            "route": "chat",
            "action": "create",
            "chat_reply": "",
            "status": "planned",
        }

    # 1. Parallel: read KB + fetch available campaigns
    import asyncio
    kb_context, available_campaigns = await asyncio.gather(
        asyncio.to_thread(
            read_relevant_kb_context,
            topic=user_query,
            workspace_id=workspace_id,
            limit=8,
        ),
        _fetch_available_campaigns(workspace_id),
    )

    # 2. LLM classifies intent and plans the campaign
    llm = get_llm(temperature=0.1)

    tool_hint = state.get("tool_hint") or ""
    tool_hint_section = ""
    # Only pass tool_hint to LLM when user explicitly selected a non-default tool
    if tool_hint and tool_hint not in ("full_workflow", ""):
        tool_hint_map = {
            "research": "research_only",
            "generate_content": "content_only",
            "post_to_channel": "post_existing",
        }
        mapped = tool_hint_map.get(tool_hint, "")
        if mapped:
            tool_hint_section = f"\nUI tool hint from user: '{tool_hint}' → prefer route '{mapped}' unless the message clearly indicates otherwise.\n"

    # Format conversation history for the planner so it understands prior context
    history = state.get("conversation_history") or []
    if history:
        history_lines = "\n".join(
            f"  [{m['role'].upper()}]: {m['content'][:300]}" for m in history[-10:]
        )
        history_section = f"\n─── Recent conversation history (newest last) ───\n{history_lines}\n"
    else:
        history_section = ""

    prompt = f"""
You are the campaign planner for a growth-driven marketing platform.

User message: {user_query}
{tool_hint_section}{history_section}
─── Available campaigns already in the system ───
{json.dumps(available_campaigns[:6], indent=2, default=str)[:2000]}

─── Prior KB growth signals on this topic ───
{json.dumps(kb_context, indent=2)[:1500]}

Classify the user's INTENT and build a plan.

Intent options:
  chat             — GENERIC or conversational message unrelated to campaigns
                     (greetings, questions about the platform, small talk, "what can you do?",
                      "hi", "hello", "thanks", general questions etc.).
                     Use this when the message does NOT request campaign work.
  research_only    — user wants insights/research only, no content or posting
  content_only     — user provides a brief and wants content created, skip research
  research_content — user wants research + content created but NOT posted yet
  post_existing    — user wants to publish content from a PREVIOUS campaign
                     (e.g. "post last week's campaign", "post the LinkedIn draft we made")
  full_campaign    — full loop: research → create content → A/B test → publish → analytics

For post_existing:
  - Match the user's description to one of the available campaigns above
  - Set matched_campaign_id, matched_campaign_name, target_platforms

For content creation routes:
  - Set hypothesis, test_design, primary_metric, objective
  - Use prior KB signals to inform the test design

Return JSON only:
{{
  "route": "chat",
  "chat_response": "friendly reply if route is chat, else null",
  "objective": "engagement",
  "hypothesis": "...",
  "test_design": "...",
  "primary_metric": "ctr",
  "platforms": ["linkedin"],
  "matched_campaign_id": null,
  "matched_campaign_name": null,
  "target_platforms": null,
  "kb_signals_used": ["..."],
  "reasoning": "..."
}}
"""
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    raw = coerce_llm_content(response.content) if hasattr(response, "content") else str(response)

    plan = _parse_json(raw)
    # Default to 'chat' on parse failure so a quota error never triggers a full campaign run
    route = plan.get("route") or "chat"
    action = "publish_existing" if route == "post_existing" else "create"

    logger.info("planner | completed route=%s action=%s", route, action)
    return {
        "kb_context": kb_context,
        "available_campaigns": available_campaigns,
        "plan": plan,
        "route": route,
        "action": action,
        "chat_reply": plan.get("chat_response") or "",
        "status": "planned",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Team runner stubs — each invokes the compiled subgraph
# ─────────────────────────────────────────────────────────────────────────────

async def run_research_team(state: SupervisorState) -> dict:
    logger.info("research_team | starting query=%r", state.get("user_query", "")[:80])
    from app.agents.research_graph import research_graph

    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    research_input = {
        "user_query": state["user_query"],
        "workspace_context": {
            "workspace_id": state.get("workspace_id"),
            "kb_context": state.get("kb_context", {}),
            "campaign_plan": state.get("plan", {}),
        },
        "routing": "to_content_agent",
        "agent_findings": [],
        "alert_context": None,
        "orchestrator_plan": None,
        "synthesis_result": None,
        "user_report": None,
        "content_brief": None,
    }

    result = await research_graph.ainvoke(research_input, config)
    logger.info("research_team | completed")
    # Return ONLY changed fields
    return {"research_result": result, "status": "creating_content"}


async def run_content_team(state: SupervisorState) -> dict:
    logger.info("content_team | starting")
    from app.agents.content_graph import content_graph

    content_brief = state.get("research_result", {}).get("content_brief") or {}
    if hasattr(content_brief, "model_dump"):
        content_brief = content_brief.model_dump()
    elif hasattr(content_brief, "__dict__"):
        content_brief = dict(content_brief)

    content_input = {
        "content_brief": content_brief,
        "kb_context": state.get("kb_context", {}),
        "platforms": state.get("plan", {}).get("platforms", ["linkedin"]),
        "hypothesis": state.get("plan", {}).get("hypothesis", ""),
    }

    result = await content_graph.ainvoke(content_input)
    logger.info("content_team | completed variants=%d", len(result.get("variants", [])))
    # Return ONLY changed fields
    return {
        "content_result": {
            "content_brief": content_brief,
            "variants": result.get("variants", []),
            "strategy": result.get("strategy", {}),
        },
        "status": "launching_campaign",
    }


async def run_campaign_team(state: SupervisorState) -> dict:
    logger.info("campaign_team | starting campaign_id=%s", state.get("campaign_id"))
    from app.agents.campaign_graph import campaign_graph

    campaign_id = state.get("campaign_id") or str(uuid.uuid4())
    content_brief = state.get("content_result", {}).get("content_brief", {})
    content_brief["kb_context"] = state.get("kb_context", {})

    result = await campaign_graph.ainvoke({
        "campaign_id": campaign_id,
        "workspace_id": state.get("workspace_id", ""),
        "content_brief": content_brief,
        "variants": state.get("content_result", {}).get("variants", []),
        "hypothesis": state.get("plan", {}).get("hypothesis", ""),
        "primary_metric": state.get("plan", {}).get("primary_metric", "ctr"),
    })
    logger.info("campaign_team | completed campaign_id=%s status=%s",
                campaign_id, dict(result).get("status"))
    # Return ONLY changed fields
    return {"campaign_result": dict(result), "status": "completed"}


# ─────────────────────────────────────────────────────────────────────────────
# Post-existing node — publishes a previously created campaign
# ─────────────────────────────────────────────────────────────────────────────

async def post_existing_node(state: SupervisorState) -> dict:
    """
    Handles "post last week's campaign to LinkedIn" type requests.
    Looks up the matched campaign's content and returns it ready-to-post.
    Does NOT publish automatically — returns a publish_confirmation card
    so the user can review and confirm.
    """
    import asyncio
    from app.db import get_db_cursor

    plan = state.get("plan", {})
    campaign_id = plan.get("matched_campaign_id")
    campaign_name = plan.get("matched_campaign_name", "the matched campaign")
    target_platforms = plan.get("target_platforms") or plan.get("platforms", ["linkedin"])

    if not campaign_id:
        return {
            "campaign_result": {
                "action": "post_existing",
                "error": "Could not identify which campaign to post. Please specify the campaign name or creation date.",
                "available_campaigns": [
                    {"name": c["name"], "created_at": c["created_at"], "platforms": c["platforms"]}
                    for c in (state.get("available_campaigns") or [])[:5]
                ],
            },
            "status": "needs_clarification",
        }

    def _load_content():
        try:
            with get_db_cursor() as cursor:
                cursor.execute("""
                    SELECT
                        cc.id, cc.platform, cc.headline, cc.body, cc.cta,
                        cc.content_type, cc.design_spec, cc.content_brief
                    FROM campaign_content cc
                    WHERE cc.campaign_id = %s::uuid
                      AND (%s IS NULL OR cc.platform = ANY(%s::text[]))
                    ORDER BY cc.is_base DESC, cc.created_at ASC
                """, (campaign_id, target_platforms, target_platforms))
                return cursor.fetchall()
        except Exception:
            return []

    rows = await asyncio.to_thread(_load_content)
    content_items = [
        {
            "id": str(r["id"]),
            "platform": r["platform"],
            "headline": r["headline"],
            "body": r["body"],
            "cta": r["cta"],
            "content_type": r["content_type"],
        }
        for r in rows
    ]

    return {
        "campaign_result": {
            "action": "post_existing",
            "campaign_id": campaign_id,
            "campaign_name": campaign_name,
            "target_platforms": target_platforms,
            "content_to_post": content_items,
            "status": "ready_to_confirm",
            "message": (
                f"Found '{campaign_name}'. {len(content_items)} content item(s) ready to post "
                f"to {', '.join(target_platforms)}. Review and confirm to publish."
            ),
        },
        "status": "awaiting_confirmation",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Routing logic
# ─────────────────────────────────────────────────────────────────────────────

async def chat_node(state: SupervisorState) -> dict:
    """
    Lightweight node for generic / conversational messages.
    Always calls the LLM so responses feel natural and varied.
    """
    reply = state.get("chat_reply") or ""
    if not reply:
        llm = get_llm(temperature=0.7)
        system_msg = SystemMessage(content=(
            "You are Xynera, an AI growth and marketing assistant. "
            "You help users plan campaigns, research markets, and create content. "
            "Be concise, friendly, and helpful. Do not use markdown unless asked."
        ))
        # Reconstruct prior turns as LangChain messages for context
        history = state.get("conversation_history") or []
        prior_messages = []
        for m in history[-8:]:
            role = m.get("role", "")
            content = m.get("content", "")
            if role == "user":
                prior_messages.append(HumanMessage(content=content))
            elif role == "assistant":
                prior_messages.append(AIMessage(content=content))
        prior_messages.append(HumanMessage(content=state.get("user_query", "Hello")))
        response = await llm.ainvoke([system_msg] + prior_messages)
        reply = coerce_llm_content(response.content) if hasattr(response, "content") else str(response)
    # Strip <think> blocks (reasoning models)
    import re as _re
    reply = _re.sub(r"<think>[\s\S]*?</think>", "", reply, flags=_re.IGNORECASE).strip()
    logger.info("chat_node | reply_len=%d", len(reply))
    return {"chat_reply": reply, "status": "completed"}


def route_after_plan(state: SupervisorState) -> str:
    """First routing decision — right after the planner runs."""
    route = state.get("route", "full_campaign")
    if route == "chat":
        return "chat"
    if route == "post_existing":
        return "post_existing"
    return "research_team"


def route_after_research(state: SupervisorState) -> str:
    route = state.get("route", "full_campaign")
    if route == "research_only":
        return END
    return "content_team"


def route_after_content(state: SupervisorState) -> str:
    route = state.get("route", "full_campaign")
    if route in ("research_content", "content_only"):
        return END
    return "campaign_team"


# ─────────────────────────────────────────────────────────────────────────────
# Graph wiring
# ─────────────────────────────────────────────────────────────────────────────

def build_supervisor_graph():
    builder = StateGraph(SupervisorState)

    builder.add_node("planner", planner_node)
    builder.add_node("chat", chat_node)
    builder.add_node("post_existing", post_existing_node)
    builder.add_node("research_team", run_research_team)
    builder.add_node("content_team", run_content_team)
    builder.add_node("campaign_team", run_campaign_team)

    builder.set_entry_point("planner")
    # After planning: chat shortcut, post existing content, or run research
    builder.add_conditional_edges(
        "planner",
        route_after_plan,
        {"chat": "chat", "post_existing": "post_existing", "research_team": "research_team"},
    )
    builder.add_edge("chat", END)
    builder.add_edge("post_existing", END)
    builder.add_conditional_edges(
        "research_team", route_after_research, {"content_team": "content_team", END: END}
    )
    builder.add_conditional_edges(
        "content_team", route_after_content, {"campaign_team": "campaign_team", END: END}
    )
    builder.add_edge("campaign_team", END)

    return builder.compile()


supervisor_graph = build_supervisor_graph()


def _parse_json(text) -> dict:
    import re
    text = coerce_llm_content(text)
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            pass
    return {}
