import os
import time
from contextlib import contextmanager

import psycopg2
from psycopg2 import OperationalError
from psycopg2.extras import RealDictCursor


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if not raw:
        return default

    try:
        value = int(raw)
    except ValueError:
        return default

    return value if value > 0 else default


@contextmanager
def get_db_cursor():
    """Yield a PostgreSQL cursor with commit/rollback safety."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")

    connect_timeout = _env_int("DB_CONNECT_TIMEOUT_SECONDS", 8)
    connect_attempts = _env_int("DB_CONNECT_ATTEMPTS", 3)
    retry_delay_ms = _env_int("DB_CONNECT_RETRY_DELAY_MS", 250)
    statement_timeout_ms = _env_int("DB_STATEMENT_TIMEOUT_MS", 15000)

    conn = None
    for attempt in range(connect_attempts):
        try:
            conn = psycopg2.connect(
                database_url,
                connect_timeout=connect_timeout,
                options=f"-c statement_timeout={statement_timeout_ms}",
            )
            break
        except OperationalError:
            if attempt == connect_attempts - 1:
                raise
            # Short exponential backoff smooths over transient network hiccups.
            time.sleep((retry_delay_ms / 1000.0) * (2**attempt))

    if conn is None:
        raise RuntimeError("Failed to establish database connection")

    conn.autocommit = False

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


__all__ = ["get_db_cursor"]
