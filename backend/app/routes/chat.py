from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from psycopg2 import OperationalError
from psycopg2.extras import Json

from ..db import get_db_cursor
from ..security import decode_token

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
