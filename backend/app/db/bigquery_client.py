"""
BigQuery client for the Signalynt growth loop analytics layer.

Architecture:
  Postgres post_metrics  = operational (real-time; Test Monitor reads for significance)
  BigQuery content_engagement_nested = analytics (denormalized; Analytics Agent queries for lift)

Table: brand_performance.content_engagement_nested
  - One row per post (not per snapshot)
  - metrics_history ARRAY<STRUCT<>> stores all time-series snapshots in one row
  - comments ARRAY<STRUCT<>> stores comment sentiment for Growth Signal Detector
  - PARTITION BY DATE(publish_time), CLUSTER BY experiment_id, content_type, platform

Written by: Analytics Agent at experiment conclusion (batch, not streaming).
Queried by: Analytics Agent for marginal analysis and lift calculation.
"""
from __future__ import annotations
import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_BQ_PROJECT = os.getenv("BIGQUERY_PROJECT_ID", "")
_BQ_DATASET = "brand_performance"
_BQ_TABLE = "content_engagement_nested"
_FULL_TABLE = f"{_BQ_PROJECT}.{_BQ_DATASET}.{_BQ_TABLE}"


# ─────────────────────────────────────────────────────────────────────────────
# Schema setup
# Creates dataset + table using the exact DDL from the growth loop design.
# Run once: python -m app.db.bigquery_client
# ─────────────────────────────────────────────────────────────────────────────

CREATE_TABLE_DDL = f"""
CREATE TABLE IF NOT EXISTS `{_FULL_TABLE}`
(
  -- 1. Identity & Operational Info (mirrors Postgres platform_posts registry)
  post_id      STRING NOT NULL,   -- our internal UUID
  external_id  STRING,            -- platform ID (LinkedIn URN, FB post ID, etc.)
  platform     STRING,            -- facebook | linkedin | threads | email
  content_type STRING,            -- image | video | status_update | newsletter
  publish_time TIMESTAMP,         -- when the post went live
  post_metadata JSON,             -- original text, audience targeting, subject lines

  -- 2. Experimentation Metadata (the "genetic code" of the A/B test)
  experiment_id STRING,           -- links to Postgres test_experiments.id
  test_metadata STRUCT<
    var_1_name STRING,            -- e.g. 'Hook'
    var_1_val  STRING,            -- e.g. 'Negative Constraint'
    var_2_name STRING,            -- e.g. 'Tone'
    var_2_val  STRING             -- e.g. 'Casual'
  >,

  -- 3. Metrics History (enables baseline comparisons without duplication)
  -- ARRAY so multiple time-series snapshots are stored in one row per post.
  -- Test Monitor writes to Postgres post_metrics; Analytics Agent aggregates
  -- all snapshots here at experiment conclusion.
  metrics_history ARRAY<STRUCT<
    likes        INT64,
    shares       INT64,
    impressions  INT64,
    reach        INT64,
    clicks       INT64,
    recorded_at  TIMESTAMP,       -- when this snapshot was collected
    is_snapshot  BOOLEAN          -- false = final reading, true = mid-experiment
  >>,

  -- 4. Comment Sentiment (input for the Growth Signal Detector / "Sentiment Oracle")
  -- AI-scored by the Growth Signal Detector before this record is written.
  comments ARRAY<STRUCT<
    comment_id          STRING,
    comment_text        STRING,
    sentiment_score     FLOAT64,  -- AI-generated: -1.0 to 1.0
    pain_point_category STRING    -- AI-identified theme (e.g. 'pricing', 'feature_gap')
  >>
)
PARTITION BY DATE(publish_time)
CLUSTER BY experiment_id, content_type, platform;
"""


def setup_bigquery_schema() -> None:
    """Creates the BigQuery dataset and table. Safe to call multiple times."""
    try:
        from google.cloud import bigquery
        client = bigquery.Client(project=_BQ_PROJECT)

        # Create dataset if not exists
        dataset = bigquery.Dataset(f"{_BQ_PROJECT}.{_BQ_DATASET}")
        dataset.location = "US"
        client.create_dataset(dataset, exists_ok=True)
        logger.info(f"Dataset {_BQ_DATASET} ready.")

        # Run DDL
        job = client.query(CREATE_TABLE_DDL)
        job.result()
        logger.info(f"Table {_FULL_TABLE} ready.")

    except Exception as e:
        logger.error(f"BigQuery schema setup failed: {e}")
        raise


# ─────────────────────────────────────────────────────────────────────────────
# Write — aggregates Postgres post_metrics snapshots into one BQ row per post
# ─────────────────────────────────────────────────────────────────────────────

async def write_experiment_to_bq(
    experiment_id: str,
    campaign_id: str,
    variants: list[dict],
    published_posts: list[dict],
    metrics_snapshot: list[dict],   # from Postgres post_metrics aggregation
) -> None:
    """
    Writes one row per post to BigQuery content_engagement_nested.
    Called by Analytics Agent at experiment conclusion — NOT during live monitoring.
    """
    try:
        from google.cloud import bigquery
        client = bigquery.Client(project=_BQ_PROJECT)
    except Exception as e:
        logger.warning(f"BigQuery client unavailable: {e}")
        return

    rows = []
    for post in published_posts:
        variant = _find_variant(post, variants)
        post_metrics = _metrics_for_post(post.get("platform_post_id"), metrics_snapshot)

        # Map variable_values → test_metadata struct
        var_vals = variant.get("variable_values", {}) if variant else {}
        var_keys = list(var_vals.keys())
        test_metadata = {
            "var_1_name": var_keys[0] if len(var_keys) > 0 else None,
            "var_1_val":  str(list(var_vals.values())[0]) if len(var_keys) > 0 else None,
            "var_2_name": var_keys[1] if len(var_keys) > 1 else None,
            "var_2_val":  str(list(var_vals.values())[1]) if len(var_keys) > 1 else None,
        }

        rows.append({
            "post_id":       post.get("platform_post_id", ""),
            "external_id":   post.get("platform_post_id"),
            "platform":      post.get("platform", ""),
            "content_type":  (variant.get("format") if variant else None) or "post",
            "publish_time":  post.get("published_at"),
            "post_metadata": json.dumps({
                "campaign_id":   campaign_id,
                "experiment_id": experiment_id,
                "variant_name":  variant.get("name") if variant else None,
                "content":       variant.get("content") if variant else {},
            }),
            "experiment_id":  experiment_id,
            "test_metadata":  test_metadata,
            "metrics_history": [
                {
                    "likes":       m.get("likes", 0),
                    "shares":      m.get("shares", 0),
                    "impressions": m.get("impressions", 0) or m.get("total_impressions", 0),
                    "reach":       m.get("reach", 0),
                    "clicks":      m.get("clicks", 0) or m.get("total_clicks", 0),
                    "recorded_at": m.get("recorded_at") or m.get("collected_at"),
                    "is_snapshot": True,
                }
                for m in post_metrics
            ],
            "comments": [],   # populated by Growth Signal Detector from platform API
        })

    if rows:
        errors = client.insert_rows_json(_FULL_TABLE, rows)
        if errors:
            logger.error(f"BigQuery insert errors: {errors}")
        else:
            logger.info(f"Wrote {len(rows)} rows to BigQuery for experiment {experiment_id}")


# ─────────────────────────────────────────────────────────────────────────────
# Marginal Analysis Query
# Runs on BigQuery content_engagement_nested after data is written.
# Returns lift, significance, interaction effects per variant.
# ─────────────────────────────────────────────────────────────────────────────

MARGINAL_ANALYSIS_SQL = """
WITH
-- Unnest all snapshots and get the LATEST per post
latest_snapshots AS (
  SELECT
    post_id,
    experiment_id,
    platform,
    content_type,
    test_metadata.var_1_name AS var_1_name,
    test_metadata.var_1_val  AS var_1_val,
    test_metadata.var_2_name AS var_2_name,
    test_metadata.var_2_val  AS var_2_val,
    -- Aggregate across all snapshots for this post
    SUM(m.impressions) AS total_impressions,
    SUM(m.clicks)      AS total_clicks,
    SUM(m.shares)      AS total_shares,
    SUM(m.likes)       AS total_likes,
    MAX(m.reach)       AS max_reach
  FROM `{full_table}`,
    UNNEST(metrics_history) AS m
  WHERE experiment_id = @experiment_id
  GROUP BY 1, 2, 3, 4, 5, 6, 7, 8
),

-- Aggregate per variant (var_1_val is the primary split variable)
variant_agg AS (
  SELECT
    var_1_val                                         AS variant_name,
    var_2_val                                         AS secondary_variant,
    SUM(total_impressions)                            AS impressions,
    SUM(total_clicks)                                 AS clicks,
    SUM(total_shares)                                 AS shares,
    SAFE_DIVIDE(SUM(total_clicks), SUM(total_impressions))  AS ctr,
    SAFE_DIVIDE(SUM(total_shares), SUM(total_impressions))  AS share_rate,
    COUNT(DISTINCT post_id)                           AS post_count
  FROM latest_snapshots
  GROUP BY 1, 2
),

-- Control group baseline (marked as is_control or first variant alphabetically)
control AS (
  SELECT ctr AS control_ctr, share_rate AS control_share_rate
  FROM variant_agg
  ORDER BY variant_name ASC   -- deterministic; Campaign Setup marks control
  LIMIT 1
)

SELECT
  v.variant_name,
  v.secondary_variant,
  v.impressions,
  v.clicks,
  v.ctr,
  v.share_rate,
  v.post_count,
  -- Lift vs control
  SAFE_DIVIDE(v.ctr - c.control_ctr, c.control_ctr)             AS ctr_lift,
  SAFE_DIVIDE(v.share_rate - c.control_share_rate, c.control_share_rate) AS share_lift,
  -- Marginal returns indicator: ctr / rank by impressions
  RANK() OVER (ORDER BY v.impressions DESC)                      AS impression_rank,
  -- Interaction effect flag: variants with secondary dimension
  IF(v.secondary_variant IS NOT NULL AND v.secondary_variant != '', TRUE, FALSE) AS has_interaction
FROM variant_agg v
CROSS JOIN control c
ORDER BY v.ctr DESC
"""


async def run_marginal_analysis_query(
    experiment_id: str,
    primary_metric: str = "ctr",
) -> dict:
    """
    Queries BigQuery and returns structured marginal analysis results.
    """
    try:
        from google.cloud import bigquery
        client = bigquery.Client(project=_BQ_PROJECT)
    except Exception as e:
        raise RuntimeError(f"BigQuery unavailable: {e}")

    sql = MARGINAL_ANALYSIS_SQL.format(full_table=_FULL_TABLE)
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("experiment_id", "STRING", experiment_id),
        ]
    )

    job = client.query(sql, job_config=job_config)
    rows = list(job.result())

    if not rows:
        return {"error": "no data in BigQuery for this experiment"}

    # Structure results
    variants = [dict(r) for r in rows]
    lift_key = f"{primary_metric}_lift" if f"{primary_metric}_lift" in variants[0] else "ctr_lift"

    # Winner = variant with highest lift (ignoring control itself)
    non_control = [v for v in variants if v.get("impression_rank", 0) > 1]
    winner = max(non_control, key=lambda v: v.get(lift_key, 0), default=None) if non_control else None

    # Marginal returns: if impression_rank 1 has highest lift, we're still improving;
    # if rank 1 is control, we're plateauing/diminishing
    top_by_impressions = next((v for v in variants if v.get("impression_rank") == 1), None)
    top_ctr = variants[0] if variants else {}
    marginal = (
        "diminishing" if top_by_impressions and top_by_impressions.get(lift_key, 0) <= 0
        else "plateauing" if abs(top_ctr.get(lift_key, 0)) < 0.05
        else "improving"
    )

    return {
        "winner_variant": winner.get("variant_name") if winner else None,
        "lift_vs_control": {v["variant_name"]: round(float(v.get(lift_key) or 0), 4) for v in variants},
        "statistical_significance": {},  # calculate externally using scipy if needed
        "is_significant": winner is not None and abs(float(winner.get(lift_key) or 0)) > 0.05,
        "marginal_returns": marginal,
        "interaction_effects": [v for v in variants if v.get("has_interaction")],
        "raw_variants": variants,
        "conclusion": (
            f"Variant '{winner['variant_name']}' shows {round(float(winner.get(lift_key, 0))*100, 1)}% "
            f"{primary_metric} lift vs control. Marginal returns are {marginal}."
        ) if winner else "Experiment inconclusive — insufficient data or no significant lift detected.",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _find_variant(post: dict, variants: list[dict]) -> dict | None:
    for v in variants:
        if v.get("platform") == post.get("platform"):
            if v.get("name") in (post.get("variant", {}) or {}).get("name", ""):
                return v
    return variants[0] if variants else None


def _metrics_for_post(platform_post_id: str | None, metrics: list[dict]) -> list[dict]:
    if not platform_post_id:
        return metrics
    return [m for m in metrics if m.get("platform_post_id") == platform_post_id] or metrics


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    setup_bigquery_schema()
