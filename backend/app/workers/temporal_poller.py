"""
Temporal Poller — Celery task, runs every 15 minutes.
NO LLM calls. Pure rules engine on free/cheap sources.
Only fires an LLM when a threshold is crossed (via a separate task).
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from app.workers.celery_app import celery_app
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# ─────────────────────────────────────────────────────────────────────────────
# Threshold rules — tune these without code changes if moved to DB later
# ─────────────────────────────────────────────────────────────────────────────
RULES = {
    "mention_spike":          {"threshold": 3.0,  "description": "Mention volume 3x above 7-day average"},
    "trend_acceleration":     {"threshold": 50,   "description": "Google Trends interest > 50 in last 24h"},
    "competitor_news":        {"threshold": 1,    "description": "Competitor keyword in top headlines"},
}


# ─────────────────────────────────────────────────────────────────────────────
# Main poll task (Celery Beat fires this every 15min)
# ─────────────────────────────────────────────────────────────────────────────
@celery_app.task(name="app.workers.temporal_poller.run_temporal_poll", bind=True, max_retries=2)
def run_temporal_poll(self):
    """Entry point. Runs all free-source checks synchronously."""
    import asyncio
    try:
        asyncio.run(_async_poll())
    except Exception as exc:
        logger.warning(f"Temporal poll failed: {exc}")
        raise self.retry(exc=exc, countdown=60)


async def _async_poll():
    signals: list[dict[str, Any]] = []

    signals += await _check_hackernews()
    signals += await _check_reddit()
    signals += await _check_newsapi()

    for signal in signals:
        triggered = _evaluate_rule(signal)
        if triggered:
            await _handle_alert(signal, triggered)


# ─────────────────────────────────────────────────────────────────────────────
# Source checks — no LLM, just data collection
# ─────────────────────────────────────────────────────────────────────────────

async def _check_hackernews() -> list[dict]:
    """Check HN Algolia for recent spikes in tracked keywords."""
    # In production: load tracked_keywords from workspace config in DB
    # Here: return empty list as placeholder until workspace config is wired
    return []


async def _check_reddit() -> list[dict]:
    """Check Reddit for post volume spikes in tracked subreddits."""
    # Requires PRAW — placeholder until workspace subreddit config is wired
    return []


async def _check_newsapi() -> list[dict]:
    """Check NewsAPI for competitor/category mentions in headlines."""
    if not settings.newsapi_key:
        return []

    # In production: load tracked_keywords from workspace DB config
    # Placeholder — returns empty until workspace config wired
    return []


# ─────────────────────────────────────────────────────────────────────────────
# Rules engine
# ─────────────────────────────────────────────────────────────────────────────

def _evaluate_rule(signal: dict) -> str | None:
    """
    Returns the rule name that was triggered, or None.
    All logic here — no LLM.
    """
    signal_type = signal.get("signal_type", "")
    value = signal.get("value", 0)

    if signal_type == "mention_spike" and value >= RULES["mention_spike"]["threshold"]:
        return "mention_spike"
    if signal_type == "trend_acceleration" and value >= RULES["trend_acceleration"]["threshold"]:
        return "trend_acceleration"
    if signal_type == "competitor_news" and value >= RULES["competitor_news"]["threshold"]:
        return "competitor_news"

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Alert handling — writes to DB + optionally enqueues research
# ─────────────────────────────────────────────────────────────────────────────

async def _handle_alert(signal: dict, rule_name: str):
    """
    1. Write to temporal_poller_events table
    2. Push alert to Redis pub/sub (frontend WebSocket picks it up)
    3. Enqueue a focused research run via Celery
    """
    import asyncio
    from app.core.database import AsyncSessionLocal
    from sqlalchemy import text

    alert_data = {
        "signal_type": signal.get("signal_type"),
        "tool_name": signal.get("tool_name", "unknown"),
        "raw_data": signal,
        "threshold_rule": rule_name,
        "alert_fired": True,
        "alert_sent_at": datetime.now(timezone.utc).isoformat(),
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }

    # Write to DB
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(
                text("""
                    INSERT INTO temporal_poller_events
                      (signal_type, tool_name, raw_data, threshold_rule, alert_fired, alert_sent_at, checked_at)
                    VALUES
                      (:signal_type, :tool_name, :raw_data::jsonb, :threshold_rule, :alert_fired, :alert_sent_at, :checked_at)
                """),
                {
                    "signal_type": alert_data["signal_type"],
                    "tool_name": alert_data["tool_name"],
                    "raw_data": str(signal),
                    "threshold_rule": rule_name,
                    "alert_fired": True,
                    "alert_sent_at": alert_data["alert_sent_at"],
                    "checked_at": alert_data["checked_at"],
                }
            )
            await db.commit()
    except Exception as e:
        logger.error(f"Failed to write temporal alert to DB: {e}")

    # Push to Redis for real-time frontend notification
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.redis_url)
        import json
        await r.publish("temporal_alerts", json.dumps(alert_data))
        await r.aclose()
    except Exception as e:
        logger.warning(f"Redis alert publish failed: {e}")

    # Enqueue a focused research run (Option A: just notify; Option B: auto-run)
    # Currently Option A — user sees alert and decides
    logger.info(f"Temporal alert fired: rule={rule_name}, signal={signal.get('signal_type')}")
