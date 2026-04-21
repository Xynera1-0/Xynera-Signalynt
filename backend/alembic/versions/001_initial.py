"""create confidence config and audit tables

Revision ID: 001_initial
Revises: 
Create Date: 2026-04-21
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # CONFIDENCE SCORING CONFIG                                           #
    # ------------------------------------------------------------------ #
    op.create_table(
        "tool_confidence_config",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tool_name", sa.Text, nullable=False, unique=True),
        sa.Column("base_score", sa.Numeric(4, 3), nullable=False),
        sa.Column("source_type", sa.Text, nullable=False),
        sa.Column("rationale", sa.Text, nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_by", sa.Text),
    )

    op.create_table(
        "confidence_modifiers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("modifier_key", sa.Text, nullable=False),
        sa.Column("condition", sa.Text, nullable=False),
        sa.Column("multiplier", sa.Numeric(4, 3), nullable=False),
        sa.Column("rationale", sa.Text, nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "corroboration_rules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("min_sources", sa.Integer, nullable=False),
        sa.Column("max_sources", sa.Integer, nullable=True),
        sa.Column("multiplier", sa.Numeric(4, 3), nullable=False),
        sa.Column("rationale", sa.Text),
    )

    # ------------------------------------------------------------------ #
    # SEED: tool_confidence_config                                        #
    # ------------------------------------------------------------------ #
    op.execute("""
        INSERT INTO tool_confidence_config (tool_name, base_score, source_type, rationale) VALUES
        ('meta_ad_library',   0.920, 'primary',     'Official Meta API, structured, identity-verified'),
        ('reddit_praw',       0.650, 'primary',     'Raw community signal, unfiltered, no editorial'),
        ('tavily_search',     0.720, 'aggregated',  'Aggregates multiple web sources, AI-ranked'),
        ('exa_search',        0.740, 'aggregated',  'Semantic retrieval, high relevance but no verification'),
        ('firecrawl_scrape',  0.680, 'secondary',   'Raw scrape, depends on page freshness and structure'),
        ('serpapi',           0.750, 'secondary',   'SERP data is real but interpretation is indirect'),
        ('pytrends',          0.800, 'primary',     'Direct Google signal, official trend data'),
        ('newsapi',           0.700, 'secondary',   'Headlines only, no full article content'),
        ('linkedin_ads',      0.880, 'primary',     'Official LinkedIn API, verified advertiser identity'),
        ('youtube_data_api',  0.660, 'primary',     'Comment sentiment is noisy but volume is real'),
        ('hn_algolia',        0.710, 'primary',     'HN content is curated/upvoted by practitioners'),
        ('crunchbase',        0.850, 'primary',     'Structured funding data, high accuracy'),
        ('playwright',        0.550, 'secondary',   'Scrape fallback, brittle, site-dependent'),
        ('calendarific',      0.950, 'primary',     'Authoritative cultural/holiday calendar data'),
        ('patents_api',       0.900, 'primary',     'USPTO/Google Patents, official filings'),
        ('semrush',           0.820, 'primary',     'Professional SEO/keyword platform, verified data')
    """)

    # ------------------------------------------------------------------ #
    # SEED: confidence_modifiers                                          #
    # ------------------------------------------------------------------ #
    op.execute("""
        INSERT INTO confidence_modifiers (modifier_key, condition, multiplier, rationale) VALUES
        ('recency', '24h',   1.200, 'Very fresh — strong signal'),
        ('recency', '7d',    1.100, 'Recent — reliable'),
        ('recency', '30d',   1.000, 'Baseline'),
        ('recency', '90d',   0.850, 'Aging — may be outdated'),
        ('recency', 'older', 0.650, 'Stale — treat as background only'),
        ('quote_present', 'yes', 1.100, 'Verbatim quote increases traceability'),
        ('quote_present', 'no',  0.900, 'Summarised only — slight penalty')
    """)

    # ------------------------------------------------------------------ #
    # SEED: corroboration_rules                                           #
    # ------------------------------------------------------------------ #
    op.execute("""
        INSERT INTO corroboration_rules (min_sources, max_sources, multiplier, rationale) VALUES
        (1, 1,    0.850, 'Single source — no corroboration, apply penalty'),
        (2, 3,    1.000, 'Moderate corroboration — baseline'),
        (4, 6,    1.150, 'Strong corroboration across sources'),
        (7, NULL, 1.250, 'High consensus — strong signal')
    """)

    # ------------------------------------------------------------------ #
    # AUDIT TABLES                                                        #
    # ------------------------------------------------------------------ #
    op.create_table(
        "agent_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("thread_id", sa.Text, nullable=False),        # LangGraph thread_id
        sa.Column("checkpoint_id", sa.Text),
        sa.Column("user_id", UUID(as_uuid=True)),
        sa.Column("workspace_id", UUID(as_uuid=True)),
        sa.Column("agent_name", sa.Text, nullable=False),
        sa.Column("agent_mode", sa.Text, nullable=False),       # research | create | post | monitor
        sa.Column("run_type", sa.Text, nullable=False),         # parallel_fan_out | sequential | subgraph | background
        sa.Column("status", sa.Text, nullable=False, server_default="running"),
        sa.Column("input", JSONB),
        sa.Column("output", JSONB),
        sa.Column("orchestrator_plan", JSONB),
        sa.Column("error", sa.Text),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("latency_ms", sa.Integer),
        sa.Column("tokens_input", sa.Integer),
        sa.Column("tokens_output", sa.Integer),
        sa.Column("llm_model", sa.Text),
        sa.Column("parent_run_id", UUID(as_uuid=True), sa.ForeignKey("agent_runs.id")),
    )
    op.create_index("idx_agent_runs_thread", "agent_runs", ["thread_id"])
    op.create_index("idx_agent_runs_name_status", "agent_runs", ["agent_name", "status"])

    op.create_table(
        "tool_calls",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("agent_run_id", UUID(as_uuid=True), sa.ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("thread_id", sa.Text, nullable=False),
        sa.Column("tool_name", sa.Text, nullable=False),
        sa.Column("mcp_server", sa.Text),
        sa.Column("transport", sa.Text),                        # stdio | sse | http | null (native)
        sa.Column("input", JSONB, nullable=False),
        sa.Column("output", JSONB),
        sa.Column("status", sa.Text, nullable=False, server_default="pending"),
        sa.Column("error", sa.Text),
        sa.Column("source_urls", sa.ARRAY(sa.Text)),
        sa.Column("source_names", sa.ARRAY(sa.Text)),
        sa.Column("confidence_score", sa.Numeric(4, 3)),
        sa.Column("confidence_breakdown", JSONB),
        sa.Column("called_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("latency_ms", sa.Integer),
        sa.Column("cost_usd", sa.Numeric(10, 6)),
        sa.Column("sequence", sa.Integer),
    )
    op.create_index("idx_tool_calls_agent_run", "tool_calls", ["agent_run_id"])
    op.create_index("idx_tool_calls_thread", "tool_calls", ["thread_id"])

    op.create_table(
        "temporal_poller_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", UUID(as_uuid=True)),
        sa.Column("signal_type", sa.Text, nullable=False),      # mention_spike | trend_acceleration | competitor_activity | news_break
        sa.Column("tool_name", sa.Text, nullable=False),
        sa.Column("raw_data", JSONB, nullable=False),
        sa.Column("threshold_rule", sa.Text, nullable=False),
        sa.Column("alert_fired", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("alert_sent_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("triggered_run_id", UUID(as_uuid=True), sa.ForeignKey("agent_runs.id")),
        sa.Column("checked_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("idx_poller_workspace_alert", "temporal_poller_events", ["workspace_id", "alert_fired"])


def downgrade() -> None:
    op.drop_table("temporal_poller_events")
    op.drop_table("tool_calls")
    op.drop_table("agent_runs")
    op.drop_table("corroboration_rules")
    op.drop_table("confidence_modifiers")
    op.drop_table("tool_confidence_config")
