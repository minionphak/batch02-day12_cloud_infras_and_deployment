"""Shared, lazily-created Redis client.

A single module-level client lets every part of the app (sessions, rate
limiting, cost guard) reuse one connection pool.
"""

import redis

from app.config import settings

_redis_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    """Return the shared Redis client, creating it lazily on first use.

    Returns:
        redis.Redis instance configured from settings.redis_url.
    """
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


def redis_ping() -> bool:
    """Check Redis connectivity.

    Returns:
        True if Redis responds to PING, False on any failure.
    """
    try:
        return bool(get_redis().ping())
    except Exception:
        return False
