"""
Phase 9.4 — Security Hardening Tests
Tests for rate limiting, session limiting, and input sanitization middleware.
"""

import pytest
import time
from unittest.mock import MagicMock, AsyncMock, patch


class TestRateLimitMiddleware:
    """Tests for RateLimitMiddleware."""

    def _make_middleware(self, max_requests=5):
        from backend.core.security_middleware import RateLimitMiddleware
        app = MagicMock()
        mw = RateLimitMiddleware(app, max_requests=max_requests)
        return mw

    def _make_request(self, path="/api/v1/agents", ip="192.168.1.1"):
        request = MagicMock()
        request.url.path = path
        request.client.host = ip
        return request

    @pytest.mark.asyncio
    async def test_allows_under_limit(self):
        mw = self._make_middleware(max_requests=10)
        request = self._make_request()
        call_next = AsyncMock(return_value=MagicMock(headers={}))

        response = await mw.dispatch(request, call_next)
        call_next.assert_called_once()

    @pytest.mark.asyncio
    async def test_blocks_over_limit(self):
        mw = self._make_middleware(max_requests=3)
        call_next = AsyncMock(return_value=MagicMock(headers={}))

        # Exceed the limit
        for _ in range(4):
            request = self._make_request(ip="10.0.0.1")
            response = await mw.dispatch(request, call_next)

        # 4th request should be blocked (status 429)
        assert response.status_code == 429

    @pytest.mark.asyncio
    async def test_health_check_bypasses_rate_limit(self):
        mw = self._make_middleware(max_requests=1)
        call_next = AsyncMock(return_value=MagicMock(headers={}))

        # Health check should always pass
        request = self._make_request(path="/api/health")
        response = await mw.dispatch(request, call_next)
        call_next.assert_called()

    @pytest.mark.asyncio
    async def test_different_ips_independent(self):
        mw = self._make_middleware(max_requests=2)
        call_next = AsyncMock(return_value=MagicMock(headers={}))

        # IP A: 2 requests (at limit)
        for _ in range(2):
            request = self._make_request(ip="10.0.0.1")
            await mw.dispatch(request, call_next)

        # IP B: should still be allowed
        request = self._make_request(ip="10.0.0.2")
        response = await mw.dispatch(request, call_next)
        assert call_next.call_count == 3  # All 3 should succeed


class TestInputSanitizationMiddleware:
    """Tests for InputSanitizationMiddleware."""

    def test_sanitize_script_tag(self):
        from backend.core.security_middleware import InputSanitizationMiddleware
        result = InputSanitizationMiddleware._sanitize(
            '{"name": "<script>alert(1)</script>"}'
        )
        assert "<script>" not in result
        assert "alert(1)" not in result

    def test_sanitize_javascript_protocol(self):
        from backend.core.security_middleware import InputSanitizationMiddleware
        result = InputSanitizationMiddleware._sanitize(
            '{"url": "javascript:void(0)"}'
        )
        assert "javascript:" not in result

    def test_sanitize_event_handler(self):
        from backend.core.security_middleware import InputSanitizationMiddleware
        result = InputSanitizationMiddleware._sanitize(
            '{"text": "onerror=alert(1)"}'
        )
        assert "onerror=" not in result

    def test_clean_input_unchanged(self):
        from backend.core.security_middleware import InputSanitizationMiddleware
        clean_input = '{"name": "John Doe", "role": "admin"}'
        result = InputSanitizationMiddleware._sanitize(clean_input)
        assert result == clean_input

    def test_sanitize_data_uri(self):
        from backend.core.security_middleware import InputSanitizationMiddleware
        result = InputSanitizationMiddleware._sanitize(
            '{"img": "data:text/html,<h1>hi</h1>"}'
        )
        assert "data:text/html" not in result


class TestSessionLimitMiddleware:
    """Tests for SessionLimitMiddleware."""

    def test_clear_session(self):
        from backend.core.security_middleware import SessionLimitMiddleware
        mw = SessionLimitMiddleware(MagicMock(), max_sessions=5)

        # Simulate adding sessions
        mw._sessions["user1"] = {111, 222, 333}
        mw.clear_session("user1", 222)
        assert 222 not in mw._sessions["user1"]
        assert len(mw._sessions["user1"]) == 2

    def test_clear_last_session_removes_user(self):
        from backend.core.security_middleware import SessionLimitMiddleware
        mw = SessionLimitMiddleware(MagicMock(), max_sessions=5)

        mw._sessions["user2"] = {999}
        mw.clear_session("user2", 999)
        assert "user2" not in mw._sessions


class TestTokenExpiry:
    """Tests for configurable token expiry (Phase 9.4)."""

    def test_token_expiry_uses_config(self):
        """REFRESH_TOKEN_EXPIRE_DAYS should match settings.TOKEN_EXPIRY_DAYS."""
        from backend.core.auth import REFRESH_TOKEN_EXPIRE_DAYS
        from backend.core.config import settings
        assert REFRESH_TOKEN_EXPIRE_DAYS == settings.TOKEN_EXPIRY_DAYS
