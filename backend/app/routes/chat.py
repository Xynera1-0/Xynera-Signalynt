import asyncio
import logging
import os
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from psycopg2 import OperationalError
from psycopg2.extras import Json

from ..db import get_db_cursor
from ..security import decode_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])
bearer_scheme = HTTPBearer(auto_error=False)

TOOL_TO_STATUS = {
    "research": "RESEARCHING",
    "generate_content": "GENERATING_CONTENT",
    "post_to_channel": "POSTING",
    "full_workflow": "FULL_WORKFLOW",
}

STATUS_TO_TOOL = {
    "RESEARCHING": "research",
    "GENERATING_CONTENT": "generate_content",
    "POSTING": "post_to_channel",
    "FULL_WORKFLOW": "full_workflow",
}


class SendMessageRequest(BaseModel):
    """Body for POST /chat/conversations/{id}/send"""
    message: str = Field(min_length=1)
    tool: str = Field(default="full_workflow")
    title: str = Field(default="New conversation")
    workspace_id: str = Field(default="")


class ConversationUpsertRequest(BaseModel):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    tool: str = Field(default="full_workflow")


class MessageCreateRequest(BaseModel):
    id: str = Field(min_length=1)
    role: str = Field(pattern="^(user|assistant|system)$")
    content: str = Field(min_length=1)
    tool: str | None = None
    ui_type: str | None = None
    intent_detected: str | None = None
    signal_ids: list[str] | None = None
    metadata: dict[str, Any] | None = None


def _raise_db_http_exception(exc: Exception) -> None:
    if isinstance(exc, OperationalError):
        raise HTTPException(status_code=503, detail="Database unavailable. Please try again.")

    raise HTTPException(status_code=500, detail=f"Database error: {exc}")


def _token_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing bearer token")

    if credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid auth scheme")

    try:
        payload = decode_token(credentials.credentials)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid access token")

    user_id = payload.get("sub")
    email = payload.get("email")
    if not user_id or not email:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    return {"user_id": str(user_id), "email": email}


def _ensure_conversation_owner(conversation_id: str, user_id: str) -> None:
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT id
            FROM public.conversations
            WHERE id = %s::uuid AND user_id = %s::uuid;
            """,
            (conversation_id, user_id),
        )
        row = cursor.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Conversation not found")


@router.get("/conversations")
def list_conversations(token_user=Depends(_token_user)):
    try:
        with get_db_cursor() as cursor:
            cursor.execute(
                """
                SELECT id, title, current_status, updated_at
                FROM public.conversations
                WHERE user_id = %s::uuid
                ORDER BY updated_at DESC;
                """,
                (token_user["user_id"],),
            )
            rows = cursor.fetchall()
    except Exception as exc:
        _raise_db_http_exception(exc)

    conversations = [
        {
            "id": str(row["id"]),
            "title": row["title"] or "Untitled conversation",
            "tool": STATUS_TO_TOOL.get(row.get("current_status"), "full_workflow"),
            "updated_at": row.get("updated_at"),
        }
        for row in rows
    ]

    return {"conversations": conversations}


@router.post("/conversations")
def upsert_conversation(payload: ConversationUpsertRequest, token_user=Depends(_token_user)):
    try:
        status = TOOL_TO_STATUS.get(payload.tool, "FULL_WORKFLOW")
        with get_db_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO public.conversations (id, user_id, title, current_status)
                VALUES (%s::uuid, %s::uuid, %s, %s)
                ON CONFLICT (id)
                DO UPDATE SET
                    title = EXCLUDED.title,
                    current_status = EXCLUDED.current_status,
                    updated_at = now()
                WHERE public.conversations.user_id = EXCLUDED.user_id
                RETURNING id, title, current_status, updated_at;
                """,
                (payload.id, token_user["user_id"], payload.title, status),
            )
            row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=403, detail="Conversation belongs to another user")
    except HTTPException:
        raise
    except Exception as exc:
        _raise_db_http_exception(exc)

    conversation = {
        "id": str(row["id"]),
        "title": row["title"] or "Untitled conversation",
        "tool": STATUS_TO_TOOL.get(row.get("current_status"), "full_workflow"),
        "updated_at": row.get("updated_at"),
    }

    return {"conversation": conversation}


@router.get("/conversations/{conversation_id}/messages")
def list_messages(conversation_id: str, token_user=Depends(_token_user)):
    try:
        _ensure_conversation_owner(conversation_id, token_user["user_id"])

        with get_db_cursor() as cursor:
            cursor.execute(
                """
                SELECT id, role, content, agent_name, ui_type, intent_detected, signal_ids, ui_payload, created_at
                FROM public.messages
                WHERE conversation_id = %s::uuid
                ORDER BY created_at ASC;
                """,
                (conversation_id,),
            )
            rows = cursor.fetchall()
    except HTTPException:
        raise
    except Exception as exc:
        _raise_db_http_exception(exc)

    messages = [
        {
            "id": str(row["id"]),
            "role": row["role"],
            "content": row.get("content") or "",
            "tool": row.get("agent_name"),
            "ui_type": row.get("ui_type"),
            "intent_detected": row.get("intent_detected"),
            "signal_ids": [str(item) for item in (row.get("signal_ids") or [])],
            "metadata": row.get("ui_payload") or {},
            "created_at": row.get("created_at"),
        }
        for row in rows
    ]

    return {"messages": messages}


@router.post("/conversations/{conversation_id}/messages")
def create_message(conversation_id: str, payload: MessageCreateRequest, token_user=Depends(_token_user)):
    try:
        _ensure_conversation_owner(conversation_id, token_user["user_id"])

        with get_db_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO public.messages (id, conversation_id, role, content, agent_name, ui_type, intent_detected, signal_ids, ui_payload)
                VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s::uuid[], %s)
                ON CONFLICT (id) DO NOTHING;
                """,
                (
                    payload.id,
                    conversation_id,
                    payload.role,
                    payload.content,
                    payload.tool,
                    payload.ui_type,
                    payload.intent_detected,
                    payload.signal_ids,
                    Json(payload.metadata or {}),
                ),
            )
            if payload.role == "assistant":
                flyer_image_source_url = (payload.metadata or {}).get("flyer_image_source_url")
                if flyer_image_source_url:
                    cursor.execute(
                        """
                        INSERT INTO public.artifacts (message_id, type, file_url, source_signals)
                        VALUES (%s::uuid, %s, %s, %s);
                        """,
                        (
                            payload.id,
                            "flyer",
                            flyer_image_source_url,
                            Json({"signal_ids": payload.signal_ids or []}),
                        ),
                    )
            cursor.execute(
                """
                UPDATE public.conversations
                SET updated_at = now()
                WHERE id = %s::uuid AND user_id = %s::uuid;
                """,
                (conversation_id, token_user["user_id"]),
            )
    except HTTPException:
        raise
    except Exception as exc:
        _raise_db_http_exception(exc)

    return {"status": "ok"}


# ─────────────────────────────────────────────────────────────────────────────
# POST /chat/conversations/{id}/send
# Primary chat endpoint: upserts conversation, saves user message, runs the
# full supervisor graph, saves assistant message — all in one call.
#
# Why one endpoint instead of separate agent + message calls?
# 1. Atomicity — no partial state if agent succeeds but save fails
# 2. Simplicity — frontend makes one call, gets one response
# 3. History — both messages are persisted before the response returns
# 4. thread_id — conversation_id is passed to supervisor graph so LangGraph
#    checkpoints are scoped per conversation (resumable if needed)
# ─────────────────────────────────────────────────────────────────────────────

ROUTE_TO_UI_TYPE = {
    "chat":             "text",
    "clarify":          "text",
    "research_only":    "research_brief",
    "content_only":     "variant_comparison",
    "research_content": "variant_comparison",
    "full_campaign":    "campaign_result",
    "post_existing":    "publish_confirmation",
}


def _format_graph_result(result: dict) -> tuple[str, str, dict, list]:
    """
    Converts raw supervisor graph state into (content, ui_type, ui_payload, signal_ids).
    The ui_payload is consumed by EphemeralRenderer on the frontend.
    """
    route = result.get("route", "full_campaign")
    ui_type = ROUTE_TO_UI_TYPE.get(route, "text")
    # ── chat / clarify (conversational or type-disambiguation) ───────────────
    if route in ("chat", "clarify"):
        reply = result.get("chat_reply") or "I'm here to help with your campaigns."
        import re as _re
        reply = _re.sub(r"<think>[\s\S]*?</think>", "", reply, flags=_re.IGNORECASE).strip()
        return (reply, "text", {}, [])
    # ── research_only ────────────────────────────────────────────────────────
    if route == "research_only":
        research = result.get("research_result", {})

        # user_report may be a Pydantic UserReport model or already a dict
        raw_report = research.get("user_report")
        if hasattr(raw_report, "model_dump"):
            report_dict = raw_report.model_dump()
        elif isinstance(raw_report, dict):
            report_dict = raw_report
        else:
            report_dict = {}

        summary = report_dict.get("summary") or str(raw_report or "Research complete.")
        key_insights = report_dict.get("key_insights") or []
        gaps = report_dict.get("gaps") or []
        confidence = report_dict.get("confidence") or report_dict.get("overall_confidence") or 0.0
        sources = []
        for s in (report_dict.get("sources") or []):
            if isinstance(s, dict):
                sources.append(s)
            elif hasattr(s, "model_dump"):
                sources.append(s.model_dump())

        # Build signal bars from agent findings
        signals = []
        for finding in (research.get("agent_findings") or [])[:6]:
            if isinstance(finding, dict):
                signals.append({
                    "label": finding.get("tool_name", "signal"),
                    "value": round(finding.get("confidence_score", 0) * 100),
                    "trend": f"+{round(finding.get('confidence_score', 0) * 10)}%",
                })

        return (
            summary,
            ui_type,
            {
                "summary": summary,
                "key_insights": key_insights,
                "gaps": gaps,
                "confidence": confidence,
                "sources": sources,
                "signals": signals,
            },
            [],
        )

    # ── content routes ────────────────────────────────────────────────────────
    if route in ("content_only", "research_content", "full_campaign"):
        content_result = result.get("content_result", {})
        variants = content_result.get("variants", [])
        campaign = result.get("campaign_result", {})
        growth_signals = campaign.get("growth_signals", [])
        signal_ids = [
            s.get("id") for s in growth_signals if isinstance(s, dict) and s.get("id")
        ]
        ui_variants = [
            {
                "name": v.get("name", "Variant"),
                "ctr": round(3.0 + (i * 0.5), 1),   # placeholder until real metrics arrive
                "cvr": round(1.0 + (i * 0.3), 1),
                "sentiment": "positive" if v.get("is_control") else "testing",
                "platform": v.get("platform", "linkedin"),
                "is_control": v.get("is_control", False),
                "content": v.get("content", {}),
                "flyerImageUrl": v.get("content", {}).get("flyer_image_url") or "",
            }
            for i, v in enumerate(variants)
        ]
        # First flyer image URL across all variants — stored in DB artifacts
        first_flyer_url = next(
            (v.get("content", {}).get("flyer_image_url") for v in variants
             if v.get("content", {}).get("flyer_image_url")),
            None,
        )
        summary = (
            f"{len(variants)} variants created"
            + (f" | {len(growth_signals)} growth signals detected" if growth_signals else "")
            + (f" | Campaign published and live" if route == "full_campaign" else "")
        )
        return (
            summary,
            ui_type,
            {
                "variants": ui_variants,
                "growth_signals": growth_signals,
                "flyer_image_source_url": first_flyer_url,
            },
            signal_ids,
        )

    # ── post_existing ─────────────────────────────────────────────────────────
    if route == "post_existing":
        campaign_res = result.get("campaign_result", {})
        msg = campaign_res.get("message", "Ready to post.")
        return (
            msg,
            ui_type,
            campaign_res,
            [],
        )

    # ── fallback ──────────────────────────────────────────────────────────────
    return (result.get("status", "Done"), "text", {}, [])


def _db_upsert_conversation_and_save_messages(
    conversation_id: str,
    user_id: str,
    title: str,
    tool: str,
    user_msg_id: str,
    user_content: str,
    assistant_msg_id: str,
    assistant_content: str,
    ui_type: str,
    intent_detected: str,
    signal_ids: list,
    ui_payload: dict,
) -> None:
    """Runs all DB writes in one psycopg2 transaction."""
    status = TOOL_TO_STATUS.get(tool, "FULL_WORKFLOW")
    with get_db_cursor() as cursor:
        # Upsert conversation (creates it if this is the first message)
        cursor.execute(
            """
            INSERT INTO public.conversations (id, user_id, title, current_status, thread_id)
            VALUES (%s::uuid, %s::uuid, %s, %s, %s)
            ON CONFLICT (id)
            DO UPDATE SET
                title = EXCLUDED.title,
                current_status = EXCLUDED.current_status,
                thread_id = EXCLUDED.thread_id,
                updated_at = now()
            WHERE public.conversations.user_id = EXCLUDED.user_id;
            """,
            (conversation_id, user_id, title, status, conversation_id),
        )
        # Save user message
        cursor.execute(
            """
            INSERT INTO public.messages
                (id, conversation_id, role, content, agent_name, ui_type, intent_detected, signal_ids, ui_payload)
            VALUES (%s::uuid, %s::uuid, 'user', %s, %s, 'prompt', %s, ARRAY[]::uuid[], '{}'::jsonb)
            ON CONFLICT (id) DO NOTHING;
            """,
            (user_msg_id, conversation_id, user_content, tool, intent_detected),
        )
        # Save assistant message
        cursor.execute(
            """
            INSERT INTO public.messages
                (id, conversation_id, role, content, agent_name, ui_type, intent_detected, signal_ids, ui_payload)
            VALUES (%s::uuid, %s::uuid, 'assistant', %s, 'supervisor', %s, %s, %s::uuid[], %s)
            ON CONFLICT (id) DO NOTHING;
            """,
            (
                assistant_msg_id,
                conversation_id,
                assistant_content,
                ui_type,
                intent_detected,
                [s for s in signal_ids if s],
                Json(ui_payload),
            ),
        )
        # Store flyer image as artifact if present
        flyer_url = ui_payload.get("flyer_image_source_url") if isinstance(ui_payload, dict) else None
        if flyer_url:
            cursor.execute(
                """
                INSERT INTO public.artifacts (message_id, type, file_url, source_signals)
                VALUES (%s::uuid, %s, %s, %s)
                ON CONFLICT DO NOTHING;
                """,
                (assistant_msg_id, "flyer", flyer_url, Json({"signal_ids": [s for s in signal_ids if s]})),
            )


@router.post("/conversations/{conversation_id}/send")
async def send_chat_message(
    conversation_id: str,
    payload: SendMessageRequest,
    token_user=Depends(_token_user),
):
    """
    Primary endpoint: runs the full supervisor graph and persists both messages
    in one atomic DB write. The frontend makes ONE call and receives the
    formatted assistant response ready to render.
    """
    user_id = token_user["user_id"]
    user_msg_id = str(uuid.uuid4())
    assistant_msg_id = str(uuid.uuid4())

    # Run supervisor graph (async — may take 10–60 s depending on route)
    from app.agents.supervisor_graph import supervisor_graph

    # Log which LLM provider + key will be used for this invocation
    _anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    _groq_key = os.environ.get("GROQ_API_KEY", "")
    _google_key = os.environ.get("GOOGLE_API_KEY", "")
    if _anthropic_key:
        _masked = f"sk-ant-...{_anthropic_key[-6:]}"
        logger.info("graph | LLM provider=Anthropic key=%s", _masked)
    elif _groq_key:
        _masked = f"gsk_...{_groq_key[-6:]}"
        logger.info("graph | LLM provider=Groq key=%s", _masked)
    elif _google_key:
        _masked = f"AIza...{_google_key[-6:]}"
        logger.info("graph | LLM provider=Gemini key=%s", _masked)
    else:
        logger.warning("graph | LLM provider=NONE — no API keys configured")

    # Fetch recent conversation history so agents have context from prior turns
    def _fetch_history(conv_id: str, limit: int = 12) -> list[dict]:
        try:
            with get_db_cursor() as cursor:
                cursor.execute(
                    """
                    SELECT role, content FROM public.messages
                    WHERE conversation_id = %s::uuid
                    ORDER BY created_at DESC
                    LIMIT %s;
                    """,
                    (conv_id, limit),
                )
                rows = cursor.fetchall()
            # Rows are newest-first; reverse to chronological order, exclude current user message
            return [{"role": r["role"], "content": (r["content"] or "")[:600]} for r in reversed(rows)]
        except Exception:
            return []

    conversation_history = await asyncio.to_thread(_fetch_history, conversation_id)

    try:
        graph_result = await supervisor_graph.ainvoke({
            "user_query": payload.message,
            "workspace_id": payload.workspace_id,
            "campaign_id": str(uuid.uuid4()),
            "thread_id": conversation_id,
            "tool_hint": payload.tool or "",
            "conversation_history": conversation_history,
        })
        assistant_content, ui_type, ui_payload, signal_ids = _format_graph_result(graph_result)
        intent = graph_result.get("route", payload.tool)
    except Exception as exc:
        logger.exception("Agent graph failed for query=%r", payload.message[:100])
        err_str = str(exc).lower()
        if any(m in err_str for m in ("429", "quota", "rate limit", "resource_exhausted", "resource exhausted", "too many requests")):
            assistant_content = "The AI service is currently busy. Please try again in a moment."
        else:
            assistant_content = "Something went wrong while processing your request. Please try again."
        ui_type = "text"
        ui_payload = {}
        signal_ids = []
        intent = payload.tool

    # Persist everything in one DB round-trip (run sync psycopg2 in thread)
    try:
        await asyncio.to_thread(
            _db_upsert_conversation_and_save_messages,
            conversation_id,
            user_id,
            payload.title,
            payload.tool,
            user_msg_id,
            payload.message,
            assistant_msg_id,
            assistant_content,
            ui_type,
            intent,
            signal_ids,
            ui_payload,
        )
    except Exception:
        # Non-fatal — return the agent response even if DB write fails
        pass

    return {
        "user_message_id": user_msg_id,
        "assistant_message": {
            "id": assistant_msg_id,
            "role": "assistant",
            "content": assistant_content,
            "ui_type": ui_type,
            "ui_payload": ui_payload,
            "intent_detected": intent,
            "signal_ids": signal_ids,
        },
    }
