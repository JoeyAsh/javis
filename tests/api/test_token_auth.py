"""Unit tests for API token authentication helpers in ws_server.py.

Covers:
  - _is_token_auth_enabled: env var presence/absence/whitespace/length warning.
  - _extract_request_token: Bearer header, query param, malformed header precedence.
  - auth_middleware: pass-through (no token), OPTIONS, loopback, /health, 401 flows,
    correct-token acceptance, hmac.compare_digest usage.
  - websocket_handler token gate: reject before ws.prepare, accept via ?token=, loopback pass.
  - config_token_handler: loopback vs non-loopback, token present/absent.

All external I/O is mocked. No real sockets, no real HTTP server.

Loguru note: ws_server uses loguru for all logging.  caplog only captures stdlib
``logging`` records.  For loguru assertions we add a temporary loguru sink via
``loguru_logger.add()`` and check the captured text.
"""

from __future__ import annotations

import hmac
from contextlib import contextmanager
from typing import Any, Generator
from unittest.mock import AsyncMock, patch

import pytest
from loguru import logger as loguru_logger

import api.ws_server as _ws_mod
from api.ws_server import (
    _extract_request_token,
    _is_token_auth_enabled,
    auth_middleware,
    config_token_handler,
)


# ---------------------------------------------------------------------------
# Loguru capture helper
# ---------------------------------------------------------------------------


@contextmanager
def _capture_loguru(level: str = "DEBUG") -> Generator[list[str], None, None]:
    """Context manager that captures loguru log messages into a list of strings."""
    captured: list[str] = []

    def _sink(message: Any) -> None:
        captured.append(str(message))

    sink_id = loguru_logger.add(_sink, level=level)
    try:
        yield captured
    finally:
        loguru_logger.remove(sink_id)

# ---------------------------------------------------------------------------
# Shared fakes
# ---------------------------------------------------------------------------

_VALID_TOKEN = "a" * 64  # 64-char hex-ish string — clearly >= 32 chars


class _FakeTransport:
    """Minimal asyncio transport stub for peername inspection."""

    def __init__(self, ip: str = "127.0.0.1") -> None:
        self._ip = ip

    def get_extra_info(self, key: str) -> Any:
        if key == "peername":
            return (self._ip, 12345)
        return None


class _FakeRequest:
    """Minimal stand-in for aiohttp.web.Request.

    Carries exactly the attributes read by _is_loopback, _extract_request_token,
    auth_middleware, and config_token_handler.
    """

    def __init__(
        self,
        method: str = "GET",
        path: str = "/api/config/repos",
        ip: str = "192.168.1.50",
        headers: dict[str, str] | None = None,
        query: dict[str, str] | None = None,
    ) -> None:
        self.method = method
        self.path = path
        self.transport: _FakeTransport | None = _FakeTransport(ip)
        # Build headers multidict-like object (dict is sufficient — .get is called).
        self.headers = headers or {}
        # Build rel_url with a .query dict-like object.
        _q = query or {}
        self.rel_url = _FakeRelUrl(_q)


class _FakeRelUrl:
    def __init__(self, query: dict[str, str]) -> None:
        self.query = query


# ---------------------------------------------------------------------------
# _is_token_auth_enabled
# ---------------------------------------------------------------------------


class TestIsTokenAuthEnabled:
    """Tests for _is_token_auth_enabled() — env-var parsing and validation."""

    def test_returns_false_when_env_var_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """(False, '') returned when JARVIS_API_TOKEN is absent from the environment."""
        monkeypatch.delenv("JARVIS_API_TOKEN", raising=False)
        enabled, token = _is_token_auth_enabled()
        assert enabled is False
        assert token == ""

    def test_returns_false_when_env_var_is_empty_string(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """(False, '') returned when JARVIS_API_TOKEN='' (empty string)."""
        monkeypatch.setenv("JARVIS_API_TOKEN", "")
        enabled, token = _is_token_auth_enabled()
        assert enabled is False
        assert token == ""

    def test_returns_false_when_env_var_is_whitespace_only(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """(False, '') returned and WARNING logged when JARVIS_API_TOKEN is whitespace-only."""
        monkeypatch.setenv("JARVIS_API_TOKEN", "   \t\n  ")
        with _capture_loguru("WARNING") as captured:
            enabled, token = _is_token_auth_enabled()
        assert enabled is False
        assert token == ""
        assert any("empty after strip" in line for line in captured), (
            f"Expected WARNING about whitespace-only token in loguru output; got: {captured}"
        )

    def test_returns_true_and_token_when_env_var_is_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """(True, token) returned when JARVIS_API_TOKEN is a 64-char hex string."""
        monkeypatch.setenv("JARVIS_API_TOKEN", _VALID_TOKEN)
        enabled, token = _is_token_auth_enabled()
        assert enabled is True
        assert token == _VALID_TOKEN

    def test_returns_true_and_logs_warning_when_token_shorter_than_32_chars(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """(True, token) returned and a WARNING is logged when token is < 32 chars."""
        short_token = "abc123"
        monkeypatch.setenv("JARVIS_API_TOKEN", short_token)

        with _capture_loguru("WARNING") as captured:
            enabled, token = _is_token_auth_enabled()

        assert enabled is True
        assert token == short_token
        assert any("shorter than 32 bytes" in line for line in captured), (
            f"Expected WARNING about entropy in loguru output; got: {captured}"
        )


# ---------------------------------------------------------------------------
# _extract_request_token
# ---------------------------------------------------------------------------


class TestExtractRequestToken:
    """Tests for _extract_request_token() — header vs query param extraction."""

    def test_returns_token_from_bearer_header(self) -> None:
        """Token extracted from a well-formed Authorization: Bearer <token> header."""
        req = _FakeRequest(headers={"Authorization": f"Bearer {_VALID_TOKEN}"})
        assert _extract_request_token(req) == _VALID_TOKEN  # type: ignore[arg-type]

    def test_returns_token_from_query_param_when_header_absent(self) -> None:
        """Falls through to ?token= query param when Authorization header is absent."""
        req = _FakeRequest(query={"token": _VALID_TOKEN})
        assert _extract_request_token(req) == _VALID_TOKEN  # type: ignore[arg-type]

    def test_returns_empty_when_neither_present(self) -> None:
        """Returns '' when neither Authorization header nor ?token= query param exists."""
        req = _FakeRequest()
        assert _extract_request_token(req) == ""  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        "bad_header",
        [
            "Basic abc123",          # wrong scheme — debug log expected
            "justtoken",             # no scheme at all — debug log expected
            "bearer lowercase",      # wrong case (case-sensitive) — debug log expected
        ],
    )
    def test_returns_empty_and_logs_debug_when_header_is_not_bearer_prefixed(
        self, bad_header: str
    ) -> None:
        """Non-Bearer-prefixed Authorization header returns '' and does NOT fall through to ?token=.

        A DEBUG log entry is emitted explaining the ignored header.
        """
        req = _FakeRequest(
            headers={"Authorization": bad_header},
            query={"token": "should-not-be-returned"},
        )
        with _capture_loguru("DEBUG") as captured:
            result = _extract_request_token(req)  # type: ignore[arg-type]
        assert result == "", f"Expected empty string for malformed header {bad_header!r}"
        assert any(
            "Authorization" in line or "Bearer" in line for line in captured
        ), f"Expected DEBUG log for malformed header {bad_header!r}; got: {captured}"

    def test_returns_empty_when_bearer_header_has_empty_token(self) -> None:
        """'Authorization: Bearer ' (space only, no token) returns '' without debug log.

        The code treats this as a valid-scheme-but-empty-token case — it returns ''
        without logging because the Bearer prefix is correct but yields an empty value.
        The query param is still NOT consulted (header presence wins).
        """
        req = _FakeRequest(
            headers={"Authorization": "Bearer "},
            query={"token": "should-not-be-returned"},
        )
        result = _extract_request_token(req)  # type: ignore[arg-type]
        assert result == ""

    def test_header_wins_over_query_param_when_both_present(self) -> None:
        """Authorization header is used when both header and ?token= are present with matching values.

        When both sources carry the same token no DEBUG log is emitted — we only
        warn on mismatch so that identical values don't produce false-positive noise.
        """
        req = _FakeRequest(
            headers={"Authorization": f"Bearer {_VALID_TOKEN}"},
            query={"token": _VALID_TOKEN},
        )
        with _capture_loguru("DEBUG") as captured:
            result = _extract_request_token(req)  # type: ignore[arg-type]
        assert result == _VALID_TOKEN
        assert not any("differing values" in line for line in captured), (
            "No DEBUG log expected when header and query param carry the same token"
        )

    def test_debug_log_emitted_when_header_and_query_token_differ(self) -> None:
        """DEBUG log fires when Authorization header and ?token= carry different values.

        The header value is still returned; the log is informational only.
        """
        other_token = "b" * 64
        req = _FakeRequest(
            headers={"Authorization": f"Bearer {_VALID_TOKEN}"},
            query={"token": other_token},
        )
        with _capture_loguru("DEBUG") as captured:
            result = _extract_request_token(req)  # type: ignore[arg-type]
        assert result == _VALID_TOKEN
        assert any("differing values" in line for line in captured), (
            f"Expected DEBUG log about differing values; got: {captured}"
        )


# ---------------------------------------------------------------------------
# auth_middleware
# ---------------------------------------------------------------------------


class TestAuthMiddleware:
    """Tests for the auth_middleware @web.middleware function."""

    # Shared sentinel handler that records whether it was called.

    @staticmethod
    def _make_handler(response_value: Any = "ok") -> AsyncMock:
        handler = AsyncMock(return_value=response_value)
        return handler

    @pytest.mark.asyncio
    async def test_pass_through_when_token_auth_disabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """auth_middleware is a no-op when JARVIS_API_TOKEN is unset."""
        monkeypatch.delenv("JARVIS_API_TOKEN", raising=False)
        handler = self._make_handler("downstream")
        req = _FakeRequest(ip="10.0.0.1")  # non-loopback
        result = await auth_middleware(req, handler)  # type: ignore[arg-type]
        handler.assert_called_once_with(req)
        assert result == "downstream"

    @pytest.mark.asyncio
    async def test_options_request_passes_through_unconditionally(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """OPTIONS preflight requests bypass auth unconditionally (CORS pre-flight)."""
        monkeypatch.setenv("JARVIS_API_TOKEN", _VALID_TOKEN)
        handler = self._make_handler("cors-ok")
        req = _FakeRequest(method="OPTIONS", ip="10.0.0.1")
        result = await auth_middleware(req, handler)  # type: ignore[arg-type]
        handler.assert_called_once()
        assert result == "cors-ok"

    @pytest.mark.asyncio
    async def test_loopback_request_passes_through(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Requests from 127.0.0.1 bypass auth even when JARVIS_API_TOKEN is set."""
        monkeypatch.setenv("JARVIS_API_TOKEN", _VALID_TOKEN)
        handler = self._make_handler("local-ok")
        req = _FakeRequest(ip="127.0.0.1")
        result = await auth_middleware(req, handler)  # type: ignore[arg-type]
        handler.assert_called_once_with(req)
        assert result == "local-ok"

    @pytest.mark.asyncio
    async def test_health_endpoint_public_from_non_loopback(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """/health is always public — non-loopback request without token passes."""
        monkeypatch.setenv("JARVIS_API_TOKEN", _VALID_TOKEN)
        handler = self._make_handler("health-ok")
        req = _FakeRequest(path="/health", ip="10.0.0.1")
        result = await auth_middleware(req, handler)  # type: ignore[arg-type]
        handler.assert_called_once_with(req)
        assert result == "health-ok"

    @pytest.mark.asyncio
    async def test_returns_401_from_non_loopback_without_token(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Non-loopback request without a token → 401 + WWW-Authenticate + JSON body."""
        monkeypatch.setenv("JARVIS_API_TOKEN", _VALID_TOKEN)
        handler = self._make_handler()
        req = _FakeRequest(ip="10.0.0.1")
        resp = await auth_middleware(req, handler)  # type: ignore[arg-type]
        handler.assert_not_called()
        assert resp.status == 401
        assert "Bearer" in resp.headers.get("WWW-Authenticate", "")
        assert resp.content_type == "application/json"
        import json as _json
        body = _json.loads(resp.body)
        assert body == {"error": "unauthorized"}

    @pytest.mark.asyncio
    async def test_returns_401_from_non_loopback_with_wrong_token(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Non-loopback request with incorrect token → 401."""
        monkeypatch.setenv("JARVIS_API_TOKEN", _VALID_TOKEN)
        handler = self._make_handler()
        req = _FakeRequest(
            ip="10.0.0.1",
            headers={"Authorization": "Bearer wrong-token-value"},
        )
        resp = await auth_middleware(req, handler)  # type: ignore[arg-type]
        handler.assert_not_called()
        assert resp.status == 401

    @pytest.mark.asyncio
    async def test_passes_through_with_correct_token_in_authorization_header(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Non-loopback request with correct Authorization: Bearer <token> passes."""
        monkeypatch.setenv("JARVIS_API_TOKEN", _VALID_TOKEN)
        handler = self._make_handler("authed-ok")
        req = _FakeRequest(
            ip="10.0.0.1",
            headers={"Authorization": f"Bearer {_VALID_TOKEN}"},
        )
        result = await auth_middleware(req, handler)  # type: ignore[arg-type]
        handler.assert_called_once_with(req)
        assert result == "authed-ok"

    @pytest.mark.asyncio
    async def test_passes_through_with_correct_token_in_query_param(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Non-loopback request with correct ?token= passes through."""
        monkeypatch.setenv("JARVIS_API_TOKEN", _VALID_TOKEN)
        handler = self._make_handler("query-ok")
        req = _FakeRequest(ip="10.0.0.1", query={"token": _VALID_TOKEN})
        result = await auth_middleware(req, handler)  # type: ignore[arg-type]
        handler.assert_called_once_with(req)
        assert result == "query-ok"

    @pytest.mark.asyncio
    async def test_uses_hmac_compare_digest_for_comparison(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Token comparison delegates to hmac.compare_digest (timing-safe check)."""
        monkeypatch.setenv("JARVIS_API_TOKEN", _VALID_TOKEN)
        handler = self._make_handler("ok")
        req = _FakeRequest(
            ip="10.0.0.1",
            headers={"Authorization": f"Bearer {_VALID_TOKEN}"},
        )
        with patch("hmac.compare_digest", wraps=hmac.compare_digest) as mock_cd:
            await auth_middleware(req, handler)  # type: ignore[arg-type]
        mock_cd.assert_called_once()
        # Both args passed to compare_digest must be strings (no type mismatch).
        args = mock_cd.call_args[0]
        assert all(isinstance(a, str) for a in args), (
            "hmac.compare_digest must be called with str, not bytes"
        )


# ---------------------------------------------------------------------------
# websocket_handler token gate
# ---------------------------------------------------------------------------


class _WsPreparePassedSentinel(Exception):
    """Raised by the WebSocketResponse stub once prepare() is reached.

    Defined at module level so inner classes inside test methods can reference
    it without NameError.
    """


class TestWebsocketHandlerTokenGate:
    """Tests for the auth check inside websocket_handler (before ws.prepare)."""

    @pytest.mark.asyncio
    async def test_non_loopback_without_token_raises_http_unauthorized_before_prepare(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Non-loopback WS upgrade without a token raises HTTPUnauthorized before prepare."""
        from aiohttp import web

        monkeypatch.setenv("JARVIS_API_TOKEN", _VALID_TOKEN)

        req = _FakeRequest(ip="10.0.0.1", path="/ws")

        prepare_called = False

        class _FailOnPrepare:
            async def prepare(self, _req: Any) -> None:
                nonlocal prepare_called
                prepare_called = True
                raise AssertionError("ws.prepare must not be called on auth failure")

        with patch("api.ws_server.web.WebSocketResponse", return_value=_FailOnPrepare()):
            with pytest.raises(web.HTTPUnauthorized) as exc_info:
                await _ws_mod.websocket_handler(req)  # type: ignore[arg-type]

        assert not prepare_called
        assert "Bearer" in exc_info.value.headers.get("WWW-Authenticate", "")

    @pytest.mark.asyncio
    async def test_non_loopback_with_valid_token_in_query_passes_auth(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Non-loopback WS upgrade with correct ?token= passes the auth gate."""
        monkeypatch.setenv("JARVIS_API_TOKEN", _VALID_TOKEN)

        req = _FakeRequest(
            ip="10.0.0.1",
            path="/ws",
            query={"token": _VALID_TOKEN},
        )

        prepare_called = False

        class _StubWs:
            async def prepare(self, _req: Any) -> None:
                nonlocal prepare_called
                prepare_called = True
                raise _WsPreparePassedSentinel

        with patch("api.ws_server.web.WebSocketResponse", return_value=_StubWs()):
            with pytest.raises(_WsPreparePassedSentinel):
                await _ws_mod.websocket_handler(req)  # type: ignore[arg-type]

        assert prepare_called, "ws.prepare should have been called after auth succeeded"

    @pytest.mark.asyncio
    async def test_loopback_without_token_passes_auth(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Loopback WS upgrade without a token skips the auth check (loopback exemption)."""
        monkeypatch.setenv("JARVIS_API_TOKEN", _VALID_TOKEN)

        req = _FakeRequest(ip="127.0.0.1", path="/ws")

        prepare_called = False

        class _StubWs:
            async def prepare(self, _req: Any) -> None:
                nonlocal prepare_called
                prepare_called = True
                raise _WsPreparePassedSentinel

        with patch("api.ws_server.web.WebSocketResponse", return_value=_StubWs()):
            with pytest.raises(_WsPreparePassedSentinel):
                await _ws_mod.websocket_handler(req)  # type: ignore[arg-type]

        assert prepare_called


# ---------------------------------------------------------------------------
# config_token_handler
# ---------------------------------------------------------------------------


class TestConfigTokenHandler:
    """Tests for GET /api/config/token handler."""

    @pytest.mark.asyncio
    async def test_returns_403_for_non_loopback(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Non-loopback request always gets 403 regardless of auth state."""
        monkeypatch.delenv("JARVIS_API_TOKEN", raising=False)
        req = _FakeRequest(ip="10.0.0.1", path="/api/config/token")
        resp = await config_token_handler(req)  # type: ignore[arg-type]
        assert resp.status == 403

    @pytest.mark.asyncio
    async def test_returns_403_for_non_loopback_even_when_token_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Non-loopback request gets 403 even when JARVIS_API_TOKEN is configured."""
        monkeypatch.setenv("JARVIS_API_TOKEN", _VALID_TOKEN)
        req = _FakeRequest(ip="10.0.0.1", path="/api/config/token")
        resp = await config_token_handler(req)  # type: ignore[arg-type]
        assert resp.status == 403

    @pytest.mark.asyncio
    async def test_returns_empty_token_for_loopback_when_env_unset(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Loopback caller gets {"token": ""} when JARVIS_API_TOKEN is not set."""
        monkeypatch.delenv("JARVIS_API_TOKEN", raising=False)
        req = _FakeRequest(ip="127.0.0.1", path="/api/config/token")
        resp = await config_token_handler(req)  # type: ignore[arg-type]
        assert resp.status == 200
        import json as _json
        body = _json.loads(resp.body)
        assert body == {"token": ""}

    @pytest.mark.asyncio
    async def test_returns_token_for_loopback_when_env_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Loopback caller gets {"token": "<hex>"} when JARVIS_API_TOKEN is set."""
        monkeypatch.setenv("JARVIS_API_TOKEN", _VALID_TOKEN)
        req = _FakeRequest(ip="127.0.0.1", path="/api/config/token")
        resp = await config_token_handler(req)  # type: ignore[arg-type]
        assert resp.status == 200
        import json as _json
        body = _json.loads(resp.body)
        assert body == {"token": _VALID_TOKEN}
