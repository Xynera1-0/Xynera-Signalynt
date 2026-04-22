"""
Migration 002 — Campaign execution + growth loop tables.

Covers:
  - campaigns
  - campaign_content
  - test_experiments (A/B + multivariate)
  - test_variants
  - platform_posts
  - post_metrics
  - growth_signals
  - campaign_performance_summary

Revision ID: 002_campaign_growth_loop
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "002_campaign_growth_loop"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:

    # ------------------------------------------------------------------ #
    # CAMPAIGNS                                                           #
    # ------------------------------------------------------------------ #
    op.create_table(
        "campaigns",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", UUID(as_uuid=True)),
        sa.Column("user_id", UUID(as_uuid=True)),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("objective", sa.Text),                        # awareness | engagement | conversion | retention
        sa.Column("hypothesis", sa.Text),                       # the growth hypothesis being tested
        sa.Column("target_audience", JSONB, server_default="{}"),
        sa.Column("platforms", sa.ARRAY(sa.Text)),              # ["linkedin", "instagram", ...]
        sa.Column("status", sa.Text, nullable=False, server_default="draft"),
                                                                # draft | active | paused | completed | archived
        sa.Column("research_thread_id", sa.Text),               # LangGraph thread_id for research run
        sa.Column("content_thread_id", sa.Text),                # LangGraph thread_id for content run
        sa.Column("kb_context", JSONB, server_default="{}"),    # Neo4j signals injected at campaign start
        sa.Column("start_date", sa.TIMESTAMP(timezone=True)),
        sa.Column("end_date", sa.TIMESTAMP(timezone=True)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("idx_campaigns_workspace", "campaigns", ["workspace_id"])
    op.create_index("idx_campaigns_status", "campaigns", ["status"])

    # ------------------------------------------------------------------ #
    # CAMPAIGN CONTENT                                                    #
    # Each row = one piece of content produced by the Content Team       #
    # ------------------------------------------------------------------ #
    op.create_table(
        "campaign_content",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("campaign_id", UUID(as_uuid=True), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.Text, nullable=False),
        sa.Column("content_type", sa.Text),                     # post | story | ad | email | thread
        sa.Column("body", sa.Text),
        sa.Column("headline", sa.Text),
        sa.Column("cta", sa.Text),
        sa.Column("media_urls", sa.ARRAY(sa.Text)),
        sa.Column("design_spec", JSONB, server_default="{}"),   # from design agent
        sa.Column("content_brief", JSONB, server_default="{}"), # full ContentBrief from research
        sa.Column("is_base", sa.Boolean, server_default="true"), # true = original; false = variant
        sa.Column("parent_content_id", UUID(as_uuid=True), sa.ForeignKey("campaign_content.id")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("idx_campaign_content_campaign", "campaign_content", ["campaign_id"])

    # ------------------------------------------------------------------ #
    # TEST EXPERIMENTS                                                    #
    # One experiment per test (A/B or multivariate)                      #
    # ------------------------------------------------------------------ #
    op.create_table(
        "test_experiments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("campaign_id", UUID(as_uuid=True), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("experiment_type", sa.Text, nullable=False),  # ab | multivariate
        sa.Column("hypothesis", sa.Text),                       # what this specific test is testing
        sa.Column("primary_metric", sa.Text, nullable=False),   # ctr | conversion_rate | engagement_rate | reach
        sa.Column("secondary_metrics", sa.ARRAY(sa.Text)),
        sa.Column("significance_threshold", sa.Numeric(4, 3), server_default="0.95"),  # 95% confidence
        sa.Column("min_sample_size", sa.Integer),               # calculated by power analysis
        sa.Column("status", sa.Text, nullable=False, server_default="draft"),
                                                                # draft | running | paused | concluded | invalidated
        sa.Column("winner_variant_id", UUID(as_uuid=True)),     # set when concluded
        sa.Column("conclusion_notes", sa.Text),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("concluded_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("idx_experiments_campaign", "test_experiments", ["campaign_id"])
    op.create_index("idx_experiments_status", "test_experiments", ["status"])

    # ------------------------------------------------------------------ #
    # TEST VARIANTS                                                       #
    # Each row = one variant in an experiment                             #
    # For A/B: 2 rows (control + treatment)                              #
    # For multivariate: N rows (one per combination)                     #
    # ------------------------------------------------------------------ #
    op.create_table(
        "test_variants",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("experiment_id", UUID(as_uuid=True), sa.ForeignKey("test_experiments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content_id", UUID(as_uuid=True), sa.ForeignKey("campaign_content.id"), nullable=False),
        sa.Column("name", sa.Text, nullable=False),             # e.g. "Control", "Hook B + CTA 2"
        sa.Column("is_control", sa.Boolean, server_default="false"),
        sa.Column("variable_values", JSONB, server_default="{}"),
                                                                # {"hook": "emotional", "cta": "urgency", "format": "carousel"}
        sa.Column("traffic_split", sa.Numeric(4, 3)),           # 0.5 for 50/50
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("idx_variants_experiment", "test_variants", ["experiment_id"])

    # ------------------------------------------------------------------ #
    # PLATFORM POSTS                                                      #
    # Each row = one actual post published to a platform                 #
    # ------------------------------------------------------------------ #
    op.create_table(
        "platform_posts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("campaign_id", UUID(as_uuid=True), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("variant_id", UUID(as_uuid=True), sa.ForeignKey("test_variants.id")),
        sa.Column("content_id", UUID(as_uuid=True), sa.ForeignKey("campaign_content.id"), nullable=False),
        sa.Column("platform", sa.Text, nullable=False),
        sa.Column("platform_post_id", sa.Text),                 # ID returned by platform API
        sa.Column("platform_url", sa.Text),                     # direct URL to post
        sa.Column("status", sa.Text, nullable=False, server_default="scheduled"),
                                                                # scheduled | published | failed | deleted
        sa.Column("scheduled_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("published_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("error", sa.Text),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("idx_posts_campaign", "platform_posts", ["campaign_id"])
    op.create_index("idx_posts_variant", "platform_posts", ["variant_id"])
    op.create_index("idx_posts_platform", "platform_posts", ["platform"])

    # ------------------------------------------------------------------ #
    # POST METRICS                                                        #
    # Time-series snapshots collected by Test Monitor Agent              #
    # ------------------------------------------------------------------ #
    op.create_table(
        "post_metrics",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("post_id", UUID(as_uuid=True), sa.ForeignKey("platform_posts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("variant_id", UUID(as_uuid=True), sa.ForeignKey("test_variants.id")),
        sa.Column("experiment_id", UUID(as_uuid=True), sa.ForeignKey("test_experiments.id")),
        sa.Column("collected_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        # Engagement
        sa.Column("impressions", sa.Integer),
        sa.Column("reach", sa.Integer),
        sa.Column("clicks", sa.Integer),
        sa.Column("click_through_rate", sa.Numeric(8, 6)),
        sa.Column("likes", sa.Integer),
        sa.Column("comments", sa.Integer),
        sa.Column("shares", sa.Integer),
        sa.Column("saves", sa.Integer),
        sa.Column("engagement_rate", sa.Numeric(8, 6)),
        # Conversion
        sa.Column("conversions", sa.Integer),
        sa.Column("conversion_rate", sa.Numeric(8, 6)),
        sa.Column("revenue_attributed", sa.Numeric(12, 2)),
        # Cost (for paid)
        sa.Column("spend_usd", sa.Numeric(10, 2)),
        sa.Column("cpc", sa.Numeric(8, 4)),
        sa.Column("cpm", sa.Numeric(8, 4)),
        sa.Column("roas", sa.Numeric(8, 4)),
        # Raw platform response stored for BigQuery reprocessing
        sa.Column("raw_platform_data", JSONB, server_default="{}"),
    )
    op.create_index("idx_metrics_post", "post_metrics", ["post_id"])
    op.create_index("idx_metrics_variant", "post_metrics", ["variant_id"])
    op.create_index("idx_metrics_experiment", "post_metrics", ["experiment_id"])
    op.create_index("idx_metrics_collected_at", "post_metrics", ["collected_at"])

    # ------------------------------------------------------------------ #
    # GROWTH SIGNALS                                                      #
    # Produced by Growth Signal Detector after Analytics Agent runs      #
    # ------------------------------------------------------------------ #
    op.create_table(
        "growth_signals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("campaign_id", UUID(as_uuid=True), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("experiment_id", UUID(as_uuid=True), sa.ForeignKey("test_experiments.id")),
        sa.Column("signal_type", sa.Text, nullable=False),
                                                                # variant_winner | audience_segment | content_pattern
                                                                # diminishing_returns | interaction_effect | seasonal_lift
        sa.Column("description", sa.Text, nullable=False),     # human-readable: "Emotional hook outperformed rational by 34% CTR"
        sa.Column("magnitude", sa.Numeric(8, 4)),               # effect size (e.g. 0.34 = 34% lift)
        sa.Column("confidence", sa.Numeric(4, 3)),              # statistical confidence 0.0–1.0
        sa.Column("metric", sa.Text),                           # which metric this signal is about
        sa.Column("affected_variable", sa.Text),                # which test variable drove this
        sa.Column("audience_segment", JSONB, server_default="{}"),  # who this applies to
        sa.Column("content_attributes", JSONB, server_default="{}"), # what content attributes drove it
        sa.Column("written_to_kb", sa.Boolean, server_default="false"),  # has KB Writer processed this?
        sa.Column("kb_node_id", sa.Text),                       # Neo4j node ID after writing
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("idx_growth_signals_campaign", "growth_signals", ["campaign_id"])
    op.create_index("idx_growth_signals_kb", "growth_signals", ["written_to_kb"])

    # ------------------------------------------------------------------ #
    # CAMPAIGN PERFORMANCE SUMMARY                                        #
    # End-of-campaign rollup written by Analytics Agent                  #
    # ------------------------------------------------------------------ #
    op.create_table(
        "campaign_performance_summary",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("campaign_id", UUID(as_uuid=True), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("total_impressions", sa.BigInteger),
        sa.Column("total_reach", sa.BigInteger),
        sa.Column("total_clicks", sa.BigInteger),
        sa.Column("total_conversions", sa.Integer),
        sa.Column("total_spend_usd", sa.Numeric(12, 2)),
        sa.Column("blended_ctr", sa.Numeric(8, 6)),
        sa.Column("blended_conversion_rate", sa.Numeric(8, 6)),
        sa.Column("blended_roas", sa.Numeric(8, 4)),
        sa.Column("winning_variants", JSONB, server_default="{}"),   # {experiment_id: variant_id}
        sa.Column("growth_signals_count", sa.Integer),
        sa.Column("marginal_analysis_result", JSONB, server_default="{}"),  # full BigQuery output
        sa.Column("hypothesis_validated", sa.Boolean),
        sa.Column("kb_write_status", sa.Text, server_default="pending"),    # pending | completed | failed
        sa.Column("analyst_notes", sa.Text),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("campaign_performance_summary")
    op.drop_table("growth_signals")
    op.drop_table("post_metrics")
    op.drop_table("platform_posts")
    op.drop_table("test_variants")
    op.drop_table("test_experiments")
    op.drop_table("campaign_content")
    op.drop_table("campaigns")
