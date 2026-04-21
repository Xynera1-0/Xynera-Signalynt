"""Celery application + Beat schedule for the Temporal Poller."""
from celery import Celery
from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "signalynt",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.temporal_poller"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    beat_schedule={
        "temporal-poller": {
            "task": "app.workers.temporal_poller.run_temporal_poll",
            "schedule": settings.temporal_poller_interval_seconds,
        },
    },
)
