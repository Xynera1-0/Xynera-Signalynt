"""
Test Monitor — Celery Beat task.
Polls platform metrics for active experiments at configured intervals.
Checks for statistical significance after each collection window.
Fires the Analytics Agent when significance threshold is reached or duration expires.
"""
from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timezone

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Celery task registration
# ─────────────────────────────────────────────────────────────────────────────

@celery_app.task(
    name="workers.run_test_monitor",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def run_test_monitor(self):
    """
    Scheduled by Celery Beat.
    Collects metrics for all running experiments, writes to post_metrics,
    and checks if any experiment is ready to conclude.
    """
    try:
        asyncio.run(_monitor_cycle())
    except Exception as exc:
        logger.exception("Test monitor failed")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────────────────────────────────────
# Monitor cycle
# ─────────────────────────────────────────────────────────────────────────────

async def _monitor_cycle():
    from sqlalchemy import text
    from app.core.database import get_db

    async for db in get_db():
        # 1. Fetch all running experiments with their posts
        rows = await db.execute(text("""
            SELECT
                te.id            AS experiment_id,
                te.campaign_id,
                te.primary_metric,
                te.significance_threshold,
                te.min_sample_size,
                te.started_at,
                ec.duration_days
            FROM test_experiments te
            JOIN campaigns ec ON ec.id = te.campaign_id
            WHERE te.status = 'running'
        """))
        experiments = rows.mappings().all()

        for exp in experiments:
            try:
                await _process_experiment(db, dict(exp))
            except Exception as e:
                logger.warning(f"Experiment {exp['experiment_id']} monitor error: {e}")


async def _process_experiment(db, exp: dict):
    from sqlalchemy import text

    experiment_id = exp["experiment_id"]

    # 2. Fetch published posts for this experiment
    posts_rows = await db.execute(text("""
        SELECT pp.id, pp.platform_post_id, pp.platform, pp.variant_id
        FROM platform_posts pp
        JOIN test_variants tv ON tv.id = pp.variant_id
        WHERE tv.experiment_id = :eid
          AND pp.status = 'published'
    """), {"eid": experiment_id})
    posts = posts_rows.mappings().all()

    if not posts:
        return

    # 3. Collect metrics from each platform
    for post in posts:
        metrics = await _fetch_platform_metrics(
            platform=post["platform"],
            platform_post_id=post["platform_post_id"],
        )
        if metrics:
            await db.execute(text("""
                INSERT INTO post_metrics (
                    post_id, variant_id, experiment_id,
                    impressions, reach, clicks, click_through_rate,
                    likes, comments, shares, engagement_rate,
                    raw_platform_data
                ) VALUES (
                    :post_id, :variant_id, :experiment_id,
                    :impressions, :reach, :clicks, :ctr,
                    :likes, :comments, :shares, :engagement_rate,
                    :raw::jsonb
                )
            """), {
                "post_id": str(post["id"]),
                "variant_id": str(post["variant_id"]),
                "experiment_id": experiment_id,
                "impressions": metrics.get("impressions", 0),
                "reach": metrics.get("reach", 0),
                "clicks": metrics.get("clicks", 0),
                "ctr": metrics.get("ctr", 0.0),
                "likes": metrics.get("likes", 0),
                "comments": metrics.get("comments", 0),
                "shares": metrics.get("shares", 0),
                "engagement_rate": metrics.get("engagement_rate", 0.0),
                "raw": str(metrics),
            })
    await db.commit()

    # 4. Check if experiment is ready to conclude
    ready = await _check_significance(db, experiment_id, exp)
    if ready:
        _trigger_analytics(str(exp["campaign_id"]), experiment_id)


async def _check_significance(db, experiment_id: str, exp: dict) -> bool:
    """
    Simple significance check:
    - Has min_sample_size been reached on primary metric?
    - Or has duration_days elapsed since start?
    """
    from sqlalchemy import text
    import math

    threshold = float(exp.get("significance_threshold") or 0.95)
    min_n = int(exp.get("min_sample_size") or 6400)
    started_at = exp.get("started_at")

    # Check sample size
    result = await db.execute(text("""
        SELECT SUM(pm.impressions) AS total_impressions
        FROM post_metrics pm
        WHERE pm.experiment_id = :eid
    """), {"eid": experiment_id})
    row = result.mappings().first()
    total = int(row["total_impressions"] or 0) if row else 0

    if total >= min_n:
        logger.info(f"Experiment {experiment_id}: min sample size reached ({total} >= {min_n})")
        return True

    # Check duration
    if started_at:
        duration_days = exp.get("duration_days", 7)
        elapsed = (datetime.now(timezone.utc) - started_at).days
        if elapsed >= (duration_days or 7):
            logger.info(f"Experiment {experiment_id}: duration elapsed ({elapsed} days)")
            return True

    return False


def _trigger_analytics(campaign_id: str, experiment_id: str):
    """
    Fires the analytics pipeline as a Celery task.
    The analytics agent (async) picks this up and runs BigQuery analysis.
    """
    run_analytics_pipeline.delay(campaign_id=campaign_id, experiment_id=experiment_id)
    logger.info(f"Analytics triggered for campaign {campaign_id}, experiment {experiment_id}")


@celery_app.task(name="workers.run_analytics_pipeline")
def run_analytics_pipeline(campaign_id: str, experiment_id: str):
    """
    Triggered when an experiment concludes.
    Runs the analytics → growth_signal_detector → kb_writer chain.
    """
    asyncio.run(_run_analytics_async(campaign_id, experiment_id))


async def _run_analytics_async(campaign_id: str, experiment_id: str):
    from sqlalchemy import text
    from app.core.database import get_db
    from app.agents.campaign_graph import analytics_node, growth_signal_detector_node, kb_writer_node

    # Fetch experiment metrics snapshot
    async for db in get_db():
        result = await db.execute(text("""
            SELECT
                tv.name AS variant_name,
                tv.is_control,
                tv.variable_values,
                AVG(pm.click_through_rate)    AS avg_ctr,
                AVG(pm.engagement_rate)       AS avg_engagement_rate,
                SUM(pm.clicks)                AS total_clicks,
                SUM(pm.impressions)           AS total_impressions,
                COUNT(pm.id)                  AS snapshots
            FROM post_metrics pm
            JOIN test_variants tv ON tv.id = pm.variant_id
            WHERE pm.experiment_id = :eid
            GROUP BY tv.name, tv.is_control, tv.variable_values
            ORDER BY avg_ctr DESC
        """), {"eid": experiment_id})
        metrics = [dict(r) for r in result.mappings().all()]
        break

    state = {
        "campaign_id": campaign_id,
        "workspace_id": "",
        "hypothesis": "",
        "primary_metric": "ctr",
        "metrics_snapshot": metrics,
        "content_brief": {},
        "variants": [],
        "marginal_analysis": {},
        "growth_signals": [],
    }

    state = await analytics_node(state)
    state = await growth_signal_detector_node(state)
    await kb_writer_node(state)
    logger.info(f"Analytics pipeline complete for campaign {campaign_id}")


# ─────────────────────────────────────────────────────────────────────────────
# Platform metrics fetch (stub — wire real platform SDKs here)
# ─────────────────────────────────────────────────────────────────────────────

async def _fetch_platform_metrics(platform: str, platform_post_id: str) -> dict | None:
    """
    Fetch current metrics for a post from the platform API.
    Returns None if post_id is invalid/unavailable.
    Wire: LinkedIn Ads API, Meta Graph API, Twitter/X API, etc.
    """
    if not platform_post_id or platform_post_id.startswith("mock_"):
        # Return simulated metrics for mock posts
        import random
        return {
            "impressions": random.randint(1000, 50000),
            "reach": random.randint(800, 40000),
            "clicks": random.randint(20, 2000),
            "ctr": round(random.uniform(0.01, 0.08), 4),
            "likes": random.randint(10, 500),
            "comments": random.randint(2, 100),
            "shares": random.randint(1, 50),
            "engagement_rate": round(random.uniform(0.01, 0.12), 4),
        }
    # Real platform calls go here:
    # if platform == "linkedin": return await _linkedin_metrics(platform_post_id)
    # if platform == "instagram": return await _meta_metrics(platform_post_id)
    return None
