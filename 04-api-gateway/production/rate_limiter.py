"""
In-Memory Rate Limiter

Giới hạn số request mỗi user trong 1 khoảng thời gian.
Trong production: thay bằng Redis-based rate limiter để scale.

Algorithm: Sliding Window Counter
- Mỗi user có 1 bucket
- Bucket đếm request trong window (60 giây)
- Vượt quá limit → trả về 429 Too Many Requests
"""
import time
from collections import defaultdict, deque
from fastapi import HTTPException, Request


class RateLimiter:
    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        """
        Args:
            max_requests: Số request tối đa trong window
            window_seconds: Khoảng thời gian (giây)
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        # key: user_id → deque của timestamps
        self._windows: dict[str, deque] = defaultdict(deque)

    def check(self, user_id: str) -> dict:
        """
        Kiểm tra user có vượt rate limit không.
        Raise 429 nếu vượt quá.
        Returns: dict với thông tin còn lại.
        """
        now = time.time()
        window = self._windows[user_id]

        # Loại bỏ timestamps cũ (ngoài window)
        while window and window[0] < now - self.window_seconds:
            window.popleft()

        remaining = self.max_requests - len(window)
        reset_at = int(now) + self.window_seconds

        if len(window) >= self.max_requests:
            oldest = window[0]
            retry_after = int(oldest + self.window_seconds - now) + 1
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Rate limit exceeded",
                    "limit": self.max_requests,
                    "window_seconds": self.window_seconds,
                    "retry_after_seconds": retry_after,
                },
                headers={
                    "X-RateLimit-Limit": str(self.max_requests),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_at),
                    "Retry-After": str(retry_after),
                },
            )

        # Record request
        window.append(now)

        return {
            "limit": self.max_requests,
            "remaining": remaining - 1,
            "reset_at": reset_at,
        }

    def get_stats(self, user_id: str) -> dict:
        """Trả về stats của user (không check limit)."""
        now = time.time()
        window = self._windows[user_id]
        active = sum(1 for t in window if t >= now - self.window_seconds)
        return {
            "requests_in_window": active,
            "limit": self.max_requests,
            "remaining": max(0, self.max_requests - active),
        }


# Singleton instances cho các tiers khác nhau
rate_limiter_user = RateLimiter(max_requests=10, window_seconds=60)   # User: 10 req/phút
rate_limiter_admin = RateLimiter(max_requests=100, window_seconds=60)  # Admin: 100 req/phút
