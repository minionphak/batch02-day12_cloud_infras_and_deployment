"""Monthly LLM budget guard backed by Redis.

Spending is tracked per user per calendar month under
``budget:{user_id}:{YYYY-MM}``. The key carries a 32-day TTL so usage
naturally resets each month. Redis (not memory) makes the budget correct
across scaled instances and durable across restarts.
"""

import logging
import time
from typing import Dict

import redis.exceptions
from fastapi import HTTPException

from app.config import settings
from app.logging_utils import log_event
from app.redis_client import get_redis

logger = logging.getLogger(__name__)

# GPT-4o-mini reference pricing
PRICE_PER_1K_INPUT_TOKENS = 0.00015  # $0.15 / 1M input tokens
PRICE_PER_1K_OUTPUT_TOKENS = 0.0006  # $0.60 / 1M output tokens
BUDGET_WARN_RATIO = 0.8
BUDGET_KEY_TTL_SECONDS = 32 * 24 * 3600


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 characters per token).

    Args:
        text: Input text string.

    Returns:
        Estimated token count, minimum 1.
    """
    return max(1, len(text) // 4)


def _budget_key(user_id: str) -> str:
    """Redis key for the current calendar month's spending."""
    return f"budget:{user_id}:{time.strftime('%Y-%m')}"


def check_budget(user_id: str, estimated_cost: float) -> None:
    """Reject the request if it would push the user over the monthly budget.

    Args:
        user_id: Unique user identifier.
        estimated_cost: Estimated USD cost of the upcoming request.

    Raises:
        HTTPException 402: If the monthly budget would be exceeded.
    """
    try:
        current = float(get_redis().get(_budget_key(user_id)) or 0)
    except redis.exceptions.ConnectionError:
        # Fail open with a warning rather than blocking all traffic.
        log_event(logger, "warning", "cost_guard_unavailable",
                  user_id=user_id, context="check_budget")
        return

    if current + estimated_cost > settings.monthly_budget_usd:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "Monthly budget exceeded",
                "used_usd": round(current, 6),
                "budget_usd": settings.monthly_budget_usd,
                "resets_at": "first day of next month (UTC)",
            },
        )

    if current >= BUDGET_WARN_RATIO * settings.monthly_budget_usd:
        log_event(logger, "warning", "budget_warning", user_id=user_id,
                  used_usd=round(current, 6),
                  budget_usd=settings.monthly_budget_usd)


def record_usage(user_id: str, input_tokens: int, output_tokens: int) -> float:
    """Record token usage in Redis and return the computed cost.

    Args:
        user_id: Unique user identifier.
        input_tokens: Input tokens consumed.
        output_tokens: Output tokens produced.

    Returns:
        Computed cost in USD.
    """
    cost = (input_tokens / 1000) * PRICE_PER_1K_INPUT_TOKENS \
        + (output_tokens / 1000) * PRICE_PER_1K_OUTPUT_TOKENS
    try:
        client = get_redis()
        key = _budget_key(user_id)
        client.incrbyfloat(key, cost)
        client.expire(key, BUDGET_KEY_TTL_SECONDS)
    except redis.exceptions.ConnectionError:
        log_event(logger, "warning", "cost_guard_unavailable",
                  user_id=user_id, context="record_usage")
    return cost


def get_usage(user_id: str) -> Dict:
    """Return current-month spending, budget, and remaining amount.

    Args:
        user_id: Unique user identifier.

    Returns:
        Dict with used_usd, budget_usd, and remaining_usd.
    """
    try:
        used = float(get_redis().get(_budget_key(user_id)) or 0)
    except redis.exceptions.ConnectionError:
        log_event(logger, "warning", "cost_guard_unavailable",
                  user_id=user_id, context="get_usage")
        used = 0.0

    return {
        "used_usd": round(used, 6),
        "budget_usd": settings.monthly_budget_usd,
        "remaining_usd": round(settings.monthly_budget_usd - used, 6),
    }
