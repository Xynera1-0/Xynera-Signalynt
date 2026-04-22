"""
Neo4j Knowledge Base schema setup.
Run once after connecting to the Neo4j instance.

Node types and their roles:
  Campaign         — one node per Signalynt campaign (links to BigQuery via bq_experiment_id)
  ContentVariant   — a specific content variant tested in an experiment
  GrowthSignal     — a reusable, falsifiable finding from a campaign
  AudienceSegment  — a defined audience group with response characteristics
  Topic            — a content topic / theme (slug-keyed, cross-campaign)
  Platform         — a social/publishing platform (linkedin, instagram, etc.)
  PerformancePattern — a generalised pattern derived from multiple campaigns
  SentimentPattern — recurring sentiment/pain-point pattern from comment analysis
                     (sourced from BigQuery content_engagement_nested.comments[].pain_point_category)
  Keyword          — a search keyword associated with topics
  Experiment       — an A/B or multivariate test run

Relationships (all directed):
  (ContentVariant)-[:OUTPERFORMED {lift, metric, confidence}]->(ContentVariant)
  (ContentVariant)-[:BELONGS_TO]->(Campaign)
  (ContentVariant)-[:USES_PATTERN]->(PerformancePattern)
  (GrowthSignal)-[:DETECTED_IN]->(Campaign)
  (GrowthSignal)-[:APPLIES_TO]->(Topic)
  (GrowthSignal)-[:DRIVEN_BY]->(ContentVariant)
  (AudienceSegment)-[:RESPONDED_TO {engagement_rate}]->(ContentVariant)
  (AudienceSegment)-[:SHOWED_INTENT_FOR]->(Topic)
  (AudienceSegment)-[:EXPRESSED_PAIN]->(SentimentPattern)
  (Campaign)-[:TESTED]->(Experiment)
  (Experiment)-[:PRODUCED]->(GrowthSignal)
  (PerformancePattern)-[:RELEVANT_TO]->(AudienceSegment)
  (PerformancePattern)-[:VALID_ON]->(Platform)
  (SentimentPattern)-[:OBSERVED_IN]->(ContentVariant)
  (SentimentPattern)-[:ASSOCIATED_WITH]->(Topic)
  (Keyword)-[:ASSOCIATED_WITH]->(Topic)
  (Topic)-[:DRIVES]->(GrowthSignal)

Call: python -m app.db.neo4j_schema
"""
from __future__ import annotations
import logging
from app.neo4j_db import get_neo4j_driver

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Constraints — uniqueness enforced by Neo4j
# ─────────────────────────────────────────────────────────────────────────────
CONSTRAINTS = [
    "CREATE CONSTRAINT campaign_id IF NOT EXISTS FOR (n:Campaign) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT content_variant_id IF NOT EXISTS FOR (n:ContentVariant) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT growth_signal_id IF NOT EXISTS FOR (n:GrowthSignal) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT audience_segment_id IF NOT EXISTS FOR (n:AudienceSegment) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT topic_slug IF NOT EXISTS FOR (n:Topic) REQUIRE n.slug IS UNIQUE",
    "CREATE CONSTRAINT platform_id IF NOT EXISTS FOR (n:Platform) REQUIRE n.name IS UNIQUE",
    "CREATE CONSTRAINT performance_pattern_id IF NOT EXISTS FOR (n:PerformancePattern) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT keyword_text IF NOT EXISTS FOR (n:Keyword) REQUIRE n.text IS UNIQUE",
    "CREATE CONSTRAINT experiment_id IF NOT EXISTS FOR (n:Experiment) REQUIRE n.id IS UNIQUE",
    # SentimentPattern — recurring pain-point theme detected in comment sentiment analysis
    # Sourced from BigQuery content_engagement_nested.comments[].pain_point_category
    "CREATE CONSTRAINT sentiment_pattern_id IF NOT EXISTS FOR (n:SentimentPattern) REQUIRE n.id IS UNIQUE",
]

# ─────────────────────────────────────────────────────────────────────────────
# Indexes — property lookups
# ─────────────────────────────────────────────────────────────────────────────
INDEXES = [
    "CREATE INDEX campaign_workspace IF NOT EXISTS FOR (n:Campaign) ON (n.workspace_id)",
    "CREATE INDEX campaign_status IF NOT EXISTS FOR (n:Campaign) ON (n.status)",
    "CREATE INDEX growth_signal_type IF NOT EXISTS FOR (n:GrowthSignal) ON (n.signal_type)",
    "CREATE INDEX growth_signal_confidence IF NOT EXISTS FOR (n:GrowthSignal) ON (n.confidence)",
    "CREATE INDEX content_variant_platform IF NOT EXISTS FOR (n:ContentVariant) ON (n.platform)",
    "CREATE INDEX performance_pattern_metric IF NOT EXISTS FOR (n:PerformancePattern) ON (n.metric)",
    "CREATE INDEX topic_name IF NOT EXISTS FOR (n:Topic) ON (n.name)",
    # SentimentPattern property indexes
    "CREATE INDEX sentiment_pattern_category IF NOT EXISTS FOR (n:SentimentPattern) ON (n.pain_point_category)",
    "CREATE INDEX sentiment_pattern_score IF NOT EXISTS FOR (n:SentimentPattern) ON (n.avg_sentiment_score)",
    # BigQuery linkage — lets KB queries resolve back to BQ experiment records
    "CREATE INDEX campaign_bq_experiment IF NOT EXISTS FOR (n:Campaign) ON (n.bq_experiment_id)",
    "CREATE INDEX content_variant_bq_experiment IF NOT EXISTS FOR (n:ContentVariant) ON (n.bq_experiment_id)",
]

# ─────────────────────────────────────────────────────────────────────────────
# Full-text indexes — for semantic KB queries
# ─────────────────────────────────────────────────────────────────────────────
FULLTEXT_INDEXES = [
    """CREATE FULLTEXT INDEX growth_signal_search IF NOT EXISTS
       FOR (n:GrowthSignal) ON EACH [n.description, n.affected_variable]""",
    """CREATE FULLTEXT INDEX performance_pattern_search IF NOT EXISTS
       FOR (n:PerformancePattern) ON EACH [n.description, n.pattern_name]""",
    """CREATE FULLTEXT INDEX topic_search IF NOT EXISTS
       FOR (n:Topic) ON EACH [n.name, n.description]""",
    # SentimentPattern fulltext — lets Growth Signal Detector find similar pain points across campaigns
    """CREATE FULLTEXT INDEX sentiment_pattern_search IF NOT EXISTS
       FOR (n:SentimentPattern) ON EACH [n.description, n.pain_point_category, n.example_comments]""",
]

# ─────────────────────────────────────────────────────────────────────────────
# Relationship type reference (documentation only — Neo4j doesn't enforce types)
# ─────────────────────────────────────────────────────────────────────────────
#
# Relationship types now defined in the module docstring above.


def setup_neo4j_schema() -> None:
    driver = get_neo4j_driver()
    with driver.session() as session:
        for stmt in CONSTRAINTS:
            try:
                session.run(stmt)
                logger.info(f"Applied: {stmt[:60]}...")
            except Exception as e:
                logger.warning(f"Constraint skipped (may already exist): {e}")

        for stmt in INDEXES:
            try:
                session.run(stmt)
                logger.info(f"Applied: {stmt[:60]}...")
            except Exception as e:
                logger.warning(f"Index skipped: {e}")

        for stmt in FULLTEXT_INDEXES:
            try:
                session.run(stmt)
                logger.info(f"Applied fulltext index")
            except Exception as e:
                logger.warning(f"Fulltext index skipped: {e}")

    logger.info("Neo4j KB schema setup complete.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    setup_neo4j_schema()
