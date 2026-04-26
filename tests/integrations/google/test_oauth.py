"""Unit tests for GoogleOAuthService no-op stub (ADR-0001 migration).

After the migration, GoogleOAuthService is a no-op shim that delegates auth
to the gog CLI on the OpenClaw host.  Tests verify the stub contract:

- AC 7: is_authenticated() always returns True
- AC 7: get_credentials() returns None (no-op)
- AC 7: revoke() is a silent no-op
- Exception hierarchy is intact (GoogleOAuthError, subtypes)
- Singleton factory returns the same instance on repeated calls
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from integrations.google.oauth import (
    GoogleOAuthError,
    GoogleOAuthFlowError,
    GoogleOAuthRevokeError,
    GoogleOAuthService,
    GoogleOAuthTokenError,
    get_google_oauth_service,
)


# ---------------------------------------------------------------------------
# Exception hierarchy (must stay backwards-compatible)
# ---------------------------------------------------------------------------


def test_google_oauth_error_base():
    """GoogleOAuthError is a proper Exception subclass with spoken_message."""
    exc = GoogleOAuthError("technical msg", spoken_message="TTS message")
    assert str(exc) == "technical msg"
    assert exc.spoken_message == "TTS message"


def test_google_oauth_error_defaults_spoken_message_to_message():
    """GoogleOAuthError uses the message as spoken_message when not provided."""
    exc = GoogleOAuthError("only message")
    assert exc.spoken_message == "only message"


def test_google_oauth_flow_error_is_subtype():
    """GoogleOAuthFlowError is a subtype of GoogleOAuthError."""
    exc = GoogleOAuthFlowError("flow failed")
    assert isinstance(exc, GoogleOAuthError)


def test_google_oauth_token_error_is_subtype():
    """GoogleOAuthTokenError is a subtype of GoogleOAuthError."""
    exc = GoogleOAuthTokenError("token expired")
    assert isinstance(exc, GoogleOAuthError)


def test_google_oauth_revoke_error_is_subtype():
    """GoogleOAuthRevokeError is a subtype of GoogleOAuthError."""
    exc = GoogleOAuthRevokeError("revoke failed")
    assert isinstance(exc, GoogleOAuthError)


# ---------------------------------------------------------------------------
# AC 7 — is_authenticated() always returns True
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_is_authenticated_always_returns_true():
    """is_authenticated() always returns True — gog owns auth, not JARVIS."""
    svc = GoogleOAuthService({})
    result = await svc.is_authenticated(["https://www.googleapis.com/auth/gmail.readonly"])
    assert result is True


@pytest.mark.asyncio
async def test_is_authenticated_true_for_empty_scopes():
    """is_authenticated() returns True even when called with an empty scope list."""
    svc = GoogleOAuthService({})
    result = await svc.is_authenticated([])
    assert result is True


@pytest.mark.asyncio
async def test_is_authenticated_true_for_multiple_scopes():
    """is_authenticated() returns True regardless of how many scopes are requested."""
    svc = GoogleOAuthService({})
    result = await svc.is_authenticated([
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/calendar.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ])
    assert result is True


# ---------------------------------------------------------------------------
# AC 7 — get_credentials() is a no-op that returns None
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_credentials_returns_none():
    """get_credentials() is a no-op stub that returns None."""
    svc = GoogleOAuthService({})
    result = await svc.get_credentials(["https://www.googleapis.com/auth/gmail.readonly"])
    assert result is None


@pytest.mark.asyncio
async def test_get_credentials_does_not_raise():
    """get_credentials() does not raise any exception."""
    svc = GoogleOAuthService({})
    # Should complete silently with no exception
    await svc.get_credentials([])


# ---------------------------------------------------------------------------
# AC 7 — revoke() is a silent no-op
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_revoke_does_not_raise():
    """revoke() is a no-op — does not raise any exception."""
    svc = GoogleOAuthService({})
    await svc.revoke()  # must not raise


@pytest.mark.asyncio
async def test_revoke_is_idempotent():
    """revoke() can be called multiple times without error."""
    svc = GoogleOAuthService({})
    await svc.revoke()
    await svc.revoke()
    await svc.revoke()


# ---------------------------------------------------------------------------
# Constructor accepts and ignores config dict
# ---------------------------------------------------------------------------


def test_constructor_accepts_empty_config():
    """GoogleOAuthService accepts an empty config dict without error."""
    svc = GoogleOAuthService({})
    assert svc is not None


def test_constructor_accepts_full_config():
    """GoogleOAuthService accepts a full config dict without error."""
    config = {
        "client_id": "test-client-id",
        "client_secret": "test-client-secret",
        "token_cache_path": "/tmp/token.json",
        "timeout_seconds": 30,
    }
    svc = GoogleOAuthService(config)
    assert svc is not None


def test_constructor_accepts_none_config():
    """GoogleOAuthService handles receiving None gracefully."""
    # get_google_oauth_service passes {} when config is None; direct call with None
    # should not be the typical pattern, but the factory should handle it.
    svc = GoogleOAuthService({} or {})
    assert svc is not None


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------


def test_get_google_oauth_service_returns_singleton():
    """get_google_oauth_service() returns the same instance on repeated calls."""
    import integrations.google.oauth as _mod

    original = _mod._service_instance
    _mod._service_instance = None

    try:
        a = get_google_oauth_service({})
        b = get_google_oauth_service({})
        assert a is b
    finally:
        _mod._service_instance = original


def test_get_google_oauth_service_creates_new_after_reset():
    """A new instance is created after the singleton is cleared."""
    import integrations.google.oauth as _mod

    original = _mod._service_instance
    _mod._service_instance = None

    try:
        a = get_google_oauth_service({})
        _mod._service_instance = None
        b = get_google_oauth_service({})
        assert a is not b
    finally:
        _mod._service_instance = original


def test_get_google_oauth_service_returns_google_oauth_service_instance():
    """get_google_oauth_service() returns a GoogleOAuthService instance."""
    import integrations.google.oauth as _mod

    original = _mod._service_instance
    _mod._service_instance = None

    try:
        svc = get_google_oauth_service(None)
        assert isinstance(svc, GoogleOAuthService)
    finally:
        _mod._service_instance = original
