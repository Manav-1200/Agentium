"""
Security Middleware for Agentium (Phase 9.4)

Provides:
- RateLimitMiddleware: Per-IP rate limiting via Redis
- SessionLimitMiddleware: Max concurrent sessions per user
- InputSanitizationMiddleware: Strip dangerous patterns from request bodies
"""

import re
import time
import logging
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from backend.core.config import settings

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Dangerous input patterns to sanitize
# ──────────────────────────────────────────────────────────────────────────────
_DANGEROUS_PATTERNS = [
    re.compile(r"<script\b[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL),
    re.compile(r"javascript:", re.IGNORECASE),
    re.compile(r"on\w+\s*=", re.IGNORECASE),      # onclick=, onerror=, etc.
    re.compile(r"data:text/html", re.IGNORECASE),
]


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Per-IP rate limiting using an in-memory sliding window.
    Falls back to in-memory if Redis is not available.
    Phase 9.4: Security Hardening.
    """

    def __init__(self, app, max_requests: Optional[int] = None):
        super().__init__(app)
        self.max_requests = max_requests or settings.API_RATE_LIMIT_PER_MINUTE
        self._window: dict = {}  # ip -> list[timestamp]

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health check
        if request.url.path in ("/api/health", "/health", "/docs", "/openapi.json"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        window_start = now - 60  # 1-minute window

        # Clean expired entries and append current
        timestamps = self._window.get(client_ip, [])
        timestamps = [t for t in timestamps if t > window_start]
        timestamps.append(now)
        self._window[client_ip] = timestamps

        if len(timestamps) > self.max_requests:
            logger.warning(
                f"Rate limit exceeded for {client_ip}: "
                f"{len(timestamps)} requests in 60s (limit: {self.max_requests})"
            )
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded. Please try again later.",
                    "retry_after_seconds": 60,
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(
            max(0, self.max_requests - len(timestamps))
        )
        return response


class SessionLimitMiddleware(BaseHTTPMiddleware):
    """
    Limits concurrent active sessions per user.
    Tracks sessions by (user_id, token) pairs in memory.
    Phase 9.4: Security Hardening.
    """

    def __init__(self, app, max_sessions: Optional[int] = None):
        super().__init__(app)
        self.max_sessions = max_sessions or settings.MAX_CONCURRENT_SESSIONS
        self._sessions: dict = {}  # user_id -> set[token_hash]

    async def dispatch(self, request: Request, call_next):
        # Only enforce on authenticated endpoints
        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return await call_next(request)

        token = auth_header[7:]
        token_hash = hash(token)

        # Try to extract user_id from token (lightweight, no full decode)
        try:
            from jose import jwt as jose_jwt
            payload = jose_jwt.decode(
                token, settings.SECRET_KEY, algorithms=["HS256"],
                options={"verify_exp": False}
            )
            user_id = payload.get("user_id") or payload.get("sub", "unknown")
        except Exception:
            # If decode fails, let the actual auth handler deal with it
            return await call_next(request)

        # Track sessions
        active = self._sessions.get(user_id, set())
        active.add(token_hash)
        self._sessions[user_id] = active

        if len(active) > self.max_sessions:
            logger.warning(
                f"Session limit exceeded for user {user_id}: "
                f"{len(active)} sessions (limit: {self.max_sessions})"
            )
            return JSONResponse(
                status_code=429,
                content={
                    "detail": (
                        f"Maximum {self.max_sessions} concurrent sessions "
                        f"allowed. Please log out from other devices."
                    ),
                },
            )

        return await call_next(request)

    def clear_session(self, user_id: str, token_hash: int):
        """Remove a session on logout."""
        if user_id in self._sessions:
            self._sessions[user_id].discard(token_hash)
            if not self._sessions[user_id]:
                del self._sessions[user_id]


class InputSanitizationMiddleware(BaseHTTPMiddleware):
    """
    Strips dangerous patterns (XSS vectors) from JSON request bodies.
    Phase 9.4: Security Hardening.
    """

    async def dispatch(self, request: Request, call_next):
        # Only sanitize write methods with JSON bodies
        if request.method in ("POST", "PUT", "PATCH"):
            content_type = request.headers.get("content-type", "")
            if "application/json" in content_type:
                try:
                    body = await request.body()
                    body_str = body.decode("utf-8", errors="replace")
                    sanitized = self._sanitize(body_str)

                    if sanitized != body_str:
                        logger.warning(
                            f"Input sanitization triggered for "
                            f"{request.method} {request.url.path}"
                        )
                        # Replace the request body with sanitized version
                        request._body = sanitized.encode("utf-8")
                except Exception as e:
                    logger.error(f"Input sanitization error: {e}")

        return await call_next(request)

    @staticmethod
    def _sanitize(text: str) -> str:
        """Remove dangerous patterns from text."""
        result = text
        for pattern in _DANGEROUS_PATTERNS:
            result = pattern.sub("", result)
        return result
