"""Redis-backed sliding-window rate limiter.

State lives in Redis (not process memory) so the limit holds across any
number of scaled agent instances.
"""

import logging
import time
import uuid
from typing import Dict

import redis.exceptions
from fastapi import HTTPException

from app.config import settings
from app.logging_utils import log_event
from app.redis_client import get_redis

logger = logging.getLogger(__name__)

WINDOW_SECONDS = 60
KEY_TTL_SECONDS = 120  # window + slack, keeps idle keys from lingering


def _raise_rate_limited(client, key: str, limit: int, now: int) -> None:
    """Raise HTTP 429 with standard rate-limit headers."""
    oldest = client.zrange(key, 0, 0, withscores=True)
    retry_after = int(oldest[0][1] + WINDOW_SECONDS - now) + 1 if oldest else 1
    raise HTTPException(
        status_code=429,
        detail={
            "error": "Rate limit exceeded",
            "limit": limit,
            "window_seconds": WINDOW_SECONDS,
            "retry_after_seconds": retry_after,
        },
        headers={
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": str(now + retry_after),
            "Retry-After": str(retry_after),
        },
    )


def check_rate_limit(user_id: str) -> Dict:
    """Enforce a sliding-window rate limit using a Redis sorted set.

    Args:
        user_id: Unique identifier for the user being rate-limited.

    Returns:
        Dict with 'limit' and 'remaining' keys.

    Raises:
        HTTPException 429: If the per-minute limit is exceeded.
    """
    now = int(time.time())
    limit = settings.rate_limit_per_minute
    key = f"ratelimit:{user_id}"

    try:
        client = get_redis()
        pipeline = client.pipeline()
        pipeline.zremrangebyscore(key, 0, now - WINDOW_SECONDS)
        pipeline.zcard(key)
        count = pipeline.execute()[1]

        if count >= limit:
            _raise_rate_limited(client, key, limit, now)

        pipeline = client.pipeline()
        pipeline.zadd(key, {str(uuid.uuid4()): now})
        pipeline.expire(key, KEY_TTL_SECONDS)
        pipeline.execute()

        return {"limit": limit, "remaining": limit - count - 1}

    except redis.exceptions.ConnectionError:
        # Fail open: availability over strict limiting when Redis is down.
        log_event(logger, "warning", "rate_limiter_unavailable", user_id=user_id)
        return {"limit": limit, "remaining": -1}
