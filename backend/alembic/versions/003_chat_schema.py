"""
Migration 003 — Chat / auth schema.

Formalises tables that existed only as runtime bootstraps in auth.py / chat.py.
Uses CREATE TABLE IF NOT EXISTS so this is safe to run against an existing DB.

Tables created:
  public.users             — auth users (email+password and Google OAuth)
  public.conversations     — chat threads, linked to LangGraph thread_id
  public.messages          — per-message rows (user + assistant turns)
  public.artifacts         — generated media attached to messages (flyers, images)

Relationships:
  users(1) → conversations(N) → messages(N) → artifacts(N)

NOTE: conversations.thread_id = the LangGraph thread_id used for checkpoint access.
      When we invoke the supervisor graph we pass this as the configurable thread_id.
      This lets us resume graph state for long-running campaigns.

Revision ID: 003_chat_schema
"""
from alembic import op
import sqlalchemy as sa


revision = "003_chat_schema"
down_revision = "002_campaign_growth_loop"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS public.users (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name          TEXT,
            email         TEXT UNIQUE NOT NULL,
            password_hash TEXT,
            google_sub    TEXT,
            auth_provider TEXT NOT NULL DEFAULT 'local',
            created_at    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            updated_at    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON public.users (email);")

    op.execute("""
        CREATE TABLE IF NOT EXISTS public.conversations (
            id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id        UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
            title          TEXT,
            current_status TEXT NOT NULL DEFAULT 'FULL_WORKFLOW',
            -- LangGraph thread_id — pass to graph.ainvoke configurable.thread_id
            -- so checkpoints are scoped per conversation
            thread_id      TEXT,
            -- Set when the conversation produced a campaign (links to 002 campaigns table)
            campaign_id    UUID,
            created_at     TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            updated_at     TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
        );
    """)
    # If the table already existed without thread_id / campaign_id, add them safely.
    op.execute("ALTER TABLE public.conversations ADD COLUMN IF NOT EXISTS thread_id TEXT;")
    op.execute("ALTER TABLE public.conversations ADD COLUMN IF NOT EXISTS campaign_id UUID;")
    op.execute("CREATE INDEX IF NOT EXISTS idx_conversations_user ON public.conversations (user_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_conversations_thread ON public.conversations (thread_id);")

    op.execute("""
        CREATE TABLE IF NOT EXISTS public.messages (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            conversation_id  UUID NOT NULL REFERENCES public.conversations(id) ON DELETE CASCADE,
            role             TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
            content          TEXT NOT NULL,
            agent_name       TEXT,
            -- UI rendering hints consumed by EphemeralRenderer
            ui_type          TEXT,
            -- text | research_brief | variant_comparison | signal_map |
            -- channel_selector | campaign_result | publish_confirmation | flyer | content_bundle
            intent_detected  TEXT,
            signal_ids       UUID[],
            ui_payload       JSONB NOT NULL DEFAULT '{}',
            created_at       TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_messages_conversation ON public.messages (conversation_id, created_at);")

    op.execute("""
        CREATE TABLE IF NOT EXISTS public.artifacts (
            id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            message_id     UUID NOT NULL REFERENCES public.messages(id) ON DELETE CASCADE,
            type           TEXT NOT NULL,   -- flyer | image | report | csv
            file_url       TEXT,
            source_signals JSONB NOT NULL DEFAULT '{}',
            created_at     TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_artifacts_message ON public.artifacts (message_id);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.artifacts;")
    op.execute("DROP TABLE IF EXISTS public.messages;")
    op.execute("DROP TABLE IF EXISTS public.conversations;")
    op.execute("DROP TABLE IF EXISTS public.users;")
