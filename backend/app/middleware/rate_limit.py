"""Lightweight per-user rate limiter for LLM-backed endpoints (S4).

Uses an in-memory sliding window keyed by the last 16 chars of the
Authorization header (stable per-user identity without parsing the JWT).
Sufficient for single-instance Render deploys; for multi-instance,
switch to Redis-backed counting.
"""

import time
from collections import defaultdict

from collections.abc import Callable

from fastapi import HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Maximum requests per user per window
MAX_REQUESTS: int = 30
WINDOW_SECONDS: int = 60

# Paths that consume expensive LLM / embedding resources
_RATE_LIMITED_PATHS: frozenset[str] = frozenset({"/api/chat/stream"})


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window rate limiter applied to LLM-backed endpoints only."""

    def __init__(self, app):
        super().__init__(app)
        # { identity_key: [monotonic_timestamps] }
        self._requests: dict[str, list[float]] = defaultdict(list)

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        if request.url.path not in _RATE_LIMITED_PATHS:
            return await call_next(request)

        # Derive a stable per-user key from the tail of the Bearer token.
        # This avoids full JWT parsing while still being unique per session.
        auth = request.headers.get("Authorization", "")
        key = auth[-16:] if auth else (request.client.host if request.client else "unknown")

        now = time.monotonic()
        window_start = now - WINDOW_SECONDS

        # Prune expired entries
        self._requests[key] = [t for t in self._requests[key] if t > window_start]

        if len(self._requests[key]) >= MAX_REQUESTS:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Maximum {MAX_REQUESTS} requests per {WINDOW_SECONDS}s.",
            )

        self._requests[key].append(now)
        return await call_next(request)
