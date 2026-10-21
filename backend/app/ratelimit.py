"""Tiny in-memory rate limiter for the login and register endpoints.

Why: without it anybody can try thousands of passwords per minute.
It lives in the memory of one server process, which is fine for a college
project / demo. (A real production site would use Redis or a gateway.)
"""

import os
import time
from collections import deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

# (path ends with, max attempts, per seconds)
RULES = {
    "/login": (10, 60),
    "/register": (30, 60),
}
MAX_TRACKED_KEYS = 10_000


class SlidingWindowLimiter:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.hits: dict[str, deque] = {}

    def allow(self, key: str, limit: int, window: float) -> tuple[bool, int]:
        """Returns (allowed, seconds_to_wait)."""
        now = self.clock()
        if len(self.hits) > MAX_TRACKED_KEYS:  # never let memory grow without bound
            self.hits.clear()
        queue = self.hits.setdefault(key, deque())
        while queue and now - queue[0] >= window:
            queue.popleft()
        if len(queue) >= limit:
            return False, max(1, int(window - (now - queue[0])) + 1)
        queue.append(now)
        return True, 0


def rule_for(method: str, path: str):
    if method != "POST":
        return None
    for suffix, rule in RULES.items():
        if path.rstrip("/").endswith(suffix):
            return suffix, rule
    return None


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limiter: SlidingWindowLimiter | None = None):
        super().__init__(app)
        self.limiter = limiter or SlidingWindowLimiter()
        self.disabled = os.getenv("RATE_LIMIT_DISABLED", "").strip() == "1"

    async def dispatch(self, request, call_next):
        match = None if self.disabled else rule_for(request.method, request.url.path)
        if match:
            suffix, (limit, window) = match
            client = request.client.host if request.client else "unknown"
            allowed, wait = self.limiter.allow(f"{client}:{suffix}", limit, window)
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content={"detail": f"Too many attempts. Please wait {wait} seconds and try again."},
                    headers={"Retry-After": str(wait)},
                )
        return await call_next(request)
