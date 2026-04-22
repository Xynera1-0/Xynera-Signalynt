"""
Centralised logging configuration.

Call setup_logging() once at application startup (main.py lifespan).

All modules should use:
    import logging
    logger = logging.getLogger(__name__)

The LOG_LEVEL env var (default: INFO) controls the root level.
Use DEBUG for verbose agent traces during development.

Log format:
    2026-04-22 15:30:01  INFO      app.agents.campaign_graph  campaign_setup | campaign=... starting
"""
import logging
import sys

from app.core.config import get_settings


def setup_logging() -> None:
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    fmt = "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    logging.basicConfig(
        level=level,
        format=fmt,
        datefmt=datefmt,
        stream=sys.stdout,
        force=True,  # override any handlers already added (e.g. by uvicorn)
    )

    # Keep chatty third-party libraries at WARNING unless we're in DEBUG
    if level > logging.DEBUG:
        for noisy in (
            "httpx",
            "httpcore",
            "uvicorn.access",
            "hpack",
            "asyncio",
            "neo4j",
            "google.auth",
        ):
            logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.getLogger(__name__).info(
        "Logging configured — level=%s", settings.log_level.upper()
    )
