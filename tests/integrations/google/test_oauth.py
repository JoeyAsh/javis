"""Unit tests for GoogleOAuthService — all 17 acceptance criteria covered.

All external I/O (InstalledAppFlow, Credentials, googleapiclient.discovery.build,
google.auth.transport.requests.Request, requests.post) is fully mocked.
No live network calls or real filesystem writes outside tmp_path.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------

GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.readonly"


def _make_config(tmp_path: Path, timeout: int = 30) -> dict[str, Any]:
    """Return a minimal config dict pointing cache at a tmp directory."""
    return {
        "client_id": "test-client-id",
        "client_secret": "test-client-secret",
        "token_cache_path": str(tmp_path / "google_token.json"),
        "timeout_seconds": timeout,
    }


def _write_token_cache(path: Path, *, scopes: list[str], expired: bool = False) -> None:
    """Write a synthetic token cache file."""
    data = {
        "token": "access-token-value",
        "refresh_token": "refresh-token-value",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "test-client-id",
        "client_secret": "test-client-secret",
        "scopes": scopes,
    }
    path.write_text(json.dumps(data), encoding="utf-8")


def _make_valid_creds(scopes: list[str]) -> MagicMock:
    """Build a mock Credentials object that is valid and not expired."""
    creds = MagicMock()
    creds.valid = True
    creds.expired = False
    creds.refresh_token = "refresh-token-value"
    creds.token = "access-token-value"
    creds.token_uri = "https://oauth2.googleapis.com/token"
    creds.client_id = "test-client-id"
    creds.client_secret = "test-client-secret"
    creds.scopes = set(scopes)
    return creds


def _make_expired_creds(scopes: list[str]) -> MagicMock:
    """Build a mock Credentials object that is expired but has a refresh token."""
    creds = MagicMock()
    creds.valid = False
    creds.expired = True
    creds.refresh_token = "refresh-token-value"
    creds.token = "access-token-value"
    creds.token_uri = "https://oauth2.googleapis.com/token"
    creds.client_id = "test-client-id"
    creds.client_secret = "test-client-secret"
    creds.scopes = set(scopes)
    return creds


# ---------------------------------------------------------------------------
# Import service after helpers to allow env override tests
# ---------------------------------------------------------------------------

from integrations.google.oauth import (  # noqa: E402
    GoogleOAuthFlowError,
    GoogleOAuthRevokeError,
    GoogleOAuthService,
    GoogleOAuthTokenError,
    get_google_oauth_service,
)

# ---------------------------------------------------------------------------
# AC 1: is_authenticated returns False when no cache file exists
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_is_authenticated_no_cache_file(tmp_path: Path) -> None:
    """AC 1: is_authenticated returns False without raising when cache absent."""
    svc = GoogleOAuthService(_make_config(tmp_path))
    result = await svc.is_authenticated([GMAIL_SCOPE])
    assert result is False


# ---------------------------------------------------------------------------
# AC 2: get_credentials returns cached valid credentials without triggering flow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_credentials_returns_cached_valid_token(tmp_path: Path) -> None:
    """AC 2: valid cached token is returned without interactive flow."""
    cache_path = tmp_path / "google_token.json"
    _write_token_cache(cache_path, scopes=[GMAIL_SCOPE])

    valid_creds = _make_valid_creds([GMAIL_SCOPE])

    with (
        patch(
            "integrations.google.oauth.google.oauth2.credentials.Credentials",
            return_value=valid_creds,
        ),
        patch(
            "integrations.google.oauth.InstalledAppFlow.from_client_config"
        ) as mock_flow_cls,
    ):
        svc = GoogleOAuthService(_make_config(tmp_path))
        creds = await svc.get_credentials([GMAIL_SCOPE])

    assert creds is valid_creds
    # Interactive flow must NOT have been invoked
    mock_flow_cls.assert_not_called()


# ---------------------------------------------------------------------------
# AC 3: get_credentials silently refreshes an expired token
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_credentials_silently_refreshes_expired_token(tmp_path: Path) -> None:
    """AC 3: expired token with refresh_token is refreshed silently."""
    cache_path = tmp_path / "google_token.json"
    _write_token_cache(cache_path, scopes=[GMAIL_SCOPE], expired=True)

    expired_creds = _make_expired_creds([GMAIL_SCOPE])

    with (
        patch(
            "integrations.google.oauth.google.oauth2.credentials.Credentials",
            return_value=expired_creds,
        ),
        patch("integrations.google.oauth.google.auth.transport.requests.Request"),
        patch("integrations.google.oauth.InstalledAppFlow.from_client_config") as mock_flow_cls,
    ):
        # After refresh, creds become valid
        def _do_refresh(request: Any) -> None:
            expired_creds.valid = True
            expired_creds.expired = False

        expired_creds.refresh.side_effect = _do_refresh

        svc = GoogleOAuthService(_make_config(tmp_path))
        creds = await svc.get_credentials([GMAIL_SCOPE])

    assert creds is expired_creds
    expired_creds.refresh.assert_called_once()
    mock_flow_cls.assert_not_called()
    # Cache file must still exist (was re-persisted)
    assert cache_path.exists()


# ---------------------------------------------------------------------------
# AC 4: get_credentials triggers interactive flow when no cache exists
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_credentials_triggers_flow_when_no_cache(tmp_path: Path) -> None:
    """AC 4: interactive flow is called when no token file exists."""
    new_creds = _make_valid_creds([GMAIL_SCOPE])
    mock_flow = MagicMock()
    mock_flow.run_local_server.return_value = new_creds

    with (
        patch(
            "integrations.google.oauth.InstalledAppFlow.from_client_config",
            return_value=mock_flow,
        ),
        patch("integrations.google.oauth._is_headless", return_value=False),
    ):
        svc = GoogleOAuthService(_make_config(tmp_path))
        creds = await svc.get_credentials([GMAIL_SCOPE])

    assert creds is new_creds
    mock_flow.run_local_server.assert_called_once_with(port=0)

    # Credentials must have been persisted
    cache_path = tmp_path / "google_token.json"
    assert cache_path.exists()


# ---------------------------------------------------------------------------
# AC 5: get_credentials triggers re-auth when cached scopes are insufficient
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_credentials_reauths_for_missing_scopes(tmp_path: Path) -> None:
    """AC 5: re-auth is triggered when cached token covers only subset of requested scopes."""
    cache_path = tmp_path / "google_token.json"
    # Cache covers Gmail only
    _write_token_cache(cache_path, scopes=[GMAIL_SCOPE])

    gmail_creds = _make_valid_creds([GMAIL_SCOPE])
    new_creds = _make_valid_creds([GMAIL_SCOPE, CALENDAR_SCOPE])
    mock_flow = MagicMock()
    mock_flow.run_local_server.return_value = new_creds

    with (
        patch(
            "integrations.google.oauth.google.oauth2.credentials.Credentials",
            return_value=gmail_creds,
        ),
        patch(
            "integrations.google.oauth.InstalledAppFlow.from_client_config",
            return_value=mock_flow,
        ),
        patch("integrations.google.oauth._is_headless", return_value=False),
    ):
        svc = GoogleOAuthService(_make_config(tmp_path))
        # Request both scopes — cache only has Gmail
        creds = await svc.get_credentials([GMAIL_SCOPE, CALENDAR_SCOPE])

    assert creds is new_creds
    mock_flow.run_local_server.assert_called_once()


# ---------------------------------------------------------------------------
# AC 6: interactive flow uses asyncio.to_thread (not a direct blocking call)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_interactive_flow_uses_asyncio_to_thread(tmp_path: Path) -> None:
    """AC 6: run_local_server is wrapped in asyncio.to_thread, not called directly."""
    new_creds = _make_valid_creds([GMAIL_SCOPE])
    mock_flow = MagicMock()
    mock_flow.run_local_server.return_value = new_creds

    to_thread_calls: list[str] = []
    original_to_thread = asyncio.to_thread

    async def _spy_to_thread(fn: Any, *args: Any, **kwargs: Any) -> Any:
        to_thread_calls.append(getattr(fn, "__name__", repr(fn)))
        return await original_to_thread(fn, *args, **kwargs)

    with (
        patch(
            "integrations.google.oauth.InstalledAppFlow.from_client_config",
            return_value=mock_flow,
        ),
        patch("integrations.google.oauth._is_headless", return_value=False),
        patch("integrations.google.oauth.asyncio.to_thread", side_effect=_spy_to_thread),
    ):
        svc = GoogleOAuthService(_make_config(tmp_path))
        await svc.get_credentials([GMAIL_SCOPE])

    # At least one to_thread call must target the local-server runner
    assert any("local_server" in name or "run_local" in name for name in to_thread_calls), (
        f"Expected to_thread wrapping run_local_server_flow; got calls: {to_thread_calls}"
    )


# ---------------------------------------------------------------------------
# AC 7: GoogleOAuthFlowError raised on timeout; spoken_message is non-empty
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_credentials_raises_flow_error_on_timeout(tmp_path: Path) -> None:
    """AC 7: asyncio.TimeoutError is wrapped in GoogleOAuthFlowError with spoken_message."""
    mock_flow = MagicMock()

    # Simulate timeout by having wait_for consume its coroutine argument then raise.
    # Consuming the coroutine avoids the "coroutine never awaited" RuntimeWarning
    # that occurs when wait_for raises before the inner coroutine is scheduled.
    async def _timeout_wait_for(coro: Any, timeout: Any = None) -> Any:
        coro.close()  # cleanly close without awaiting
        raise asyncio.TimeoutError

    with (
        patch(
            "integrations.google.oauth.InstalledAppFlow.from_client_config",
            return_value=mock_flow,
        ),
        patch("integrations.google.oauth._is_headless", return_value=False),
        patch("integrations.google.oauth.asyncio.wait_for", new=_timeout_wait_for),
    ):
        svc = GoogleOAuthService(_make_config(tmp_path, timeout=1))
        with pytest.raises(GoogleOAuthFlowError) as exc_info:
            await svc.get_credentials([GMAIL_SCOPE])

    assert exc_info.value.spoken_message


# ---------------------------------------------------------------------------
# AC 8: GoogleOAuthTokenError raised on RefreshError; spoken_message is non-empty
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_credentials_raises_token_error_on_refresh_failure(tmp_path: Path) -> None:
    """AC 8: RefreshError is wrapped in GoogleOAuthTokenError with spoken_message."""
    import google.auth.exceptions

    cache_path = tmp_path / "google_token.json"
    _write_token_cache(cache_path, scopes=[GMAIL_SCOPE], expired=True)

    expired_creds = _make_expired_creds([GMAIL_SCOPE])
    expired_creds.refresh.side_effect = google.auth.exceptions.RefreshError("token revoked")

    # Replace asyncio.to_thread with an async function that calls its callable
    # inline so no unawaited-coroutine RuntimeWarning is emitted by the GC.
    async def _inline_to_thread(fn: Any, *args: Any, **kwargs: Any) -> Any:
        return fn(*args, **kwargs)

    with (
        patch(
            "integrations.google.oauth.google.oauth2.credentials.Credentials",
            return_value=expired_creds,
        ),
        patch("integrations.google.oauth.google.auth.transport.requests.Request"),
        patch("integrations.google.oauth.asyncio.to_thread", new=_inline_to_thread),
    ):
        svc = GoogleOAuthService(_make_config(tmp_path))
        with pytest.raises(GoogleOAuthTokenError) as exc_info:
            await svc.get_credentials([GMAIL_SCOPE])

    assert exc_info.value.spoken_message


# ---------------------------------------------------------------------------
# AC 9: corrupt token cache is silently discarded; flow proceeds
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_corrupt_cache_discarded_and_flow_proceeds(tmp_path: Path) -> None:
    """AC 9: malformed JSON in cache is discarded; interactive flow is triggered."""
    cache_path = tmp_path / "google_token.json"
    cache_path.write_text("{ not valid json !!!", encoding="utf-8")

    new_creds = _make_valid_creds([GMAIL_SCOPE])
    mock_flow = MagicMock()
    mock_flow.run_local_server.return_value = new_creds

    with (
        patch(
            "integrations.google.oauth.InstalledAppFlow.from_client_config",
            return_value=mock_flow,
        ),
        patch("integrations.google.oauth._is_headless", return_value=False),
    ):
        svc = GoogleOAuthService(_make_config(tmp_path))
        creds = await svc.get_credentials([GMAIL_SCOPE])

    assert creds is new_creds
    mock_flow.run_local_server.assert_called_once()


# ---------------------------------------------------------------------------
# AC 10: revoke() calls revocation endpoint and deletes cache file
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_revoke_calls_endpoint_and_deletes_cache(tmp_path: Path) -> None:
    """AC 10: revoke calls Google's revocation endpoint and removes cache file."""
    cache_path = tmp_path / "google_token.json"
    _write_token_cache(cache_path, scopes=[GMAIL_SCOPE])

    valid_creds = _make_valid_creds([GMAIL_SCOPE])
    mock_response = MagicMock()
    mock_response.status_code = 200

    with (
        patch(
            "integrations.google.oauth.google.oauth2.credentials.Credentials",
            return_value=valid_creds,
        ),
        patch(
            "integrations.google.oauth.requests.post", return_value=mock_response
        ) as mock_post,
    ):
        svc = GoogleOAuthService(_make_config(tmp_path))
        await svc.revoke()

    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args
    assert "revoke" in call_kwargs[0][0]
    assert not cache_path.exists()


# ---------------------------------------------------------------------------
# AC 11: revoke() when no cache file exists does not raise
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_revoke_no_op_when_no_cache_file(tmp_path: Path) -> None:
    """AC 11: revoke is silent when there is no token cache file."""
    svc = GoogleOAuthService(_make_config(tmp_path))
    # Must not raise
    await svc.revoke()


# ---------------------------------------------------------------------------
# AC 12: build_service calls get_credentials and returns a Resource
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_service_calls_get_credentials_and_returns_resource(
    tmp_path: Path,
) -> None:
    """AC 12: build_service wraps get_credentials and returns a googleapiclient Resource."""
    valid_creds = _make_valid_creds([GMAIL_SCOPE])
    mock_resource = MagicMock()

    cache_path = tmp_path / "google_token.json"
    _write_token_cache(cache_path, scopes=[GMAIL_SCOPE])

    with (
        patch(
            "integrations.google.oauth.google.oauth2.credentials.Credentials",
            return_value=valid_creds,
        ),
        patch(
            "integrations.google.oauth.googleapiclient.discovery.build",
            return_value=mock_resource,
        ) as mock_build,
    ):
        svc = GoogleOAuthService(_make_config(tmp_path))
        resource = await svc.build_service("gmail", "v1", [GMAIL_SCOPE])

    assert resource is mock_resource
    mock_build.assert_called_once_with("gmail", "v1", credentials=valid_creds)


# ---------------------------------------------------------------------------
# AC 13: constructor reads env vars; env overrides config dict
# ---------------------------------------------------------------------------


def test_constructor_reads_env_vars_over_config(tmp_path: Path, monkeypatch: Any) -> None:
    """AC 13: GOOGLE_OAUTH_CLIENT_ID/SECRET env vars take precedence over config dict."""
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "env-client-id")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "env-client-secret")

    config = {
        "client_id": "config-client-id",
        "client_secret": "config-client-secret",
        "token_cache_path": str(tmp_path / "google_token.json"),
        "timeout_seconds": 30,
    }
    svc = GoogleOAuthService(config)
    assert svc._client_id == "env-client-id"
    assert svc._client_secret == "env-client-secret"


# ---------------------------------------------------------------------------
# AC 14: config.yaml parses without error after google: section added
# ---------------------------------------------------------------------------


def test_config_yaml_parses_with_google_section() -> None:
    """AC 14: config.yaml is valid YAML and contains the google: section."""
    import yaml

    config_path = Path(__file__).parent.parent.parent.parent / "config" / "config.yaml"
    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    assert "google" in cfg, "google: section missing from config.yaml"
    assert "token_cache_path" in cfg["google"]
    assert "timeout_seconds" in cfg["google"]
    assert isinstance(cfg["google"]["timeout_seconds"], int)


# ---------------------------------------------------------------------------
# AC 15: requirements.txt includes the three google packages
# ---------------------------------------------------------------------------


def test_requirements_txt_includes_google_packages() -> None:
    """AC 15: requirements.txt lists google-auth, google-auth-oauthlib, google-api-python-client."""
    req_path = Path(__file__).parent.parent.parent.parent / "requirements.txt"
    content = req_path.read_text(encoding="utf-8")

    assert "google-auth" in content
    assert "google-auth-oauthlib" in content
    assert "google-api-python-client" in content


# ---------------------------------------------------------------------------
# AC 16: headless detection routes to run_console instead of run_local_server
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_headless_routes_to_run_console(tmp_path: Path, monkeypatch: Any) -> None:
    """AC 16: run_console is used when DISPLAY and WAYLAND_DISPLAY are absent."""
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)

    new_creds = _make_valid_creds([GMAIL_SCOPE])
    mock_flow = MagicMock()
    mock_flow.run_console.return_value = new_creds

    with patch(
        "integrations.google.oauth.InstalledAppFlow.from_client_config",
        return_value=mock_flow,
    ):
        svc = GoogleOAuthService(_make_config(tmp_path))
        creds = await svc.get_credentials([GMAIL_SCOPE])

    assert creds is new_creds
    mock_flow.run_console.assert_called_once()
    mock_flow.run_local_server.assert_not_called()


# ---------------------------------------------------------------------------
# AC 17: concurrent get_credentials calls open only one browser window
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_concurrent_get_credentials_opens_one_flow(tmp_path: Path) -> None:
    """AC 17: two concurrent get_credentials calls result in only one InstalledAppFlow call."""
    new_creds = _make_valid_creds([GMAIL_SCOPE])
    flow_call_count = 0

    def _make_mock_flow(*args: Any, **kwargs: Any) -> MagicMock:
        nonlocal flow_call_count
        flow_call_count += 1
        mock_flow = MagicMock()
        mock_flow.run_local_server.return_value = new_creds
        return mock_flow

    with (
        patch(
            "integrations.google.oauth.InstalledAppFlow.from_client_config",
            side_effect=_make_mock_flow,
        ),
        patch("integrations.google.oauth._is_headless", return_value=False),
        # Ensure that when the second coroutine re-checks the cache after the
        # first coroutine has written it, it gets back valid credentials and
        # does NOT launch a second flow.
        patch(
            "integrations.google.oauth.google.oauth2.credentials.Credentials",
            return_value=new_creds,
        ),
    ):
        svc = GoogleOAuthService(_make_config(tmp_path))
        # Launch two coroutines simultaneously
        results = await asyncio.gather(
            svc.get_credentials([GMAIL_SCOPE]),
            svc.get_credentials([GMAIL_SCOPE]),
        )

    # Both coroutines should return valid credentials
    assert all(r is new_creds for r in results)
    # But InstalledAppFlow should have been instantiated only once
    assert flow_call_count == 1, (
        f"Expected 1 flow instantiation for concurrent calls, got {flow_call_count}"
    )


# ---------------------------------------------------------------------------
# Additional: is_authenticated returns True for valid cached token
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_is_authenticated_returns_true_for_valid_token(tmp_path: Path) -> None:
    """is_authenticated returns True when a valid, sufficient cached token exists."""
    cache_path = tmp_path / "google_token.json"
    _write_token_cache(cache_path, scopes=[GMAIL_SCOPE])

    valid_creds = _make_valid_creds([GMAIL_SCOPE])

    with patch(
        "integrations.google.oauth.google.oauth2.credentials.Credentials",
        return_value=valid_creds,
    ):
        svc = GoogleOAuthService(_make_config(tmp_path))
        result = await svc.is_authenticated([GMAIL_SCOPE])

    assert result is True


# ---------------------------------------------------------------------------
# Additional: short-form scope normalisation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_short_form_scope_is_normalised(tmp_path: Path) -> None:
    """Short-form scope strings (e.g. 'gmail.readonly') are expanded before comparison."""
    cache_path = tmp_path / "google_token.json"
    _write_token_cache(cache_path, scopes=[GMAIL_SCOPE])

    valid_creds = _make_valid_creds([GMAIL_SCOPE])

    with patch(
        "integrations.google.oauth.google.oauth2.credentials.Credentials",
        return_value=valid_creds,
    ):
        svc = GoogleOAuthService(_make_config(tmp_path))
        # Pass short-form scope — should NOT trigger re-auth
        result = await svc.is_authenticated(["gmail.readonly"])

    assert result is True


# ---------------------------------------------------------------------------
# Additional: revoke raises GoogleOAuthRevokeError on HTTP error and still deletes cache
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_revoke_raises_on_http_error_but_deletes_cache(tmp_path: Path) -> None:
    """Revocation HTTP failure raises GoogleOAuthRevokeError; cache file is still deleted."""
    cache_path = tmp_path / "google_token.json"
    _write_token_cache(cache_path, scopes=[GMAIL_SCOPE])

    valid_creds = _make_valid_creds([GMAIL_SCOPE])
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = "token_revoked"

    with (
        patch(
            "integrations.google.oauth.google.oauth2.credentials.Credentials",
            return_value=valid_creds,
        ),
        patch(
            "integrations.google.oauth.requests.post", return_value=mock_response
        ),
    ):
        svc = GoogleOAuthService(_make_config(tmp_path))
        with pytest.raises(GoogleOAuthRevokeError) as exc_info:
            await svc.revoke()

    assert exc_info.value.spoken_message
    # Cache file must be removed even when revocation call fails
    assert not cache_path.exists()


# ---------------------------------------------------------------------------
# Critical 2: revoke raises GoogleOAuthRevokeError on network error; cache deleted
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_revoke_raises_on_network_error_but_deletes_cache(tmp_path: Path) -> None:
    """Network failure during revocation raises GoogleOAuthRevokeError; cache is still deleted."""
    import requests as _requests

    cache_path = tmp_path / "google_token.json"
    _write_token_cache(cache_path, scopes=[GMAIL_SCOPE])

    valid_creds = _make_valid_creds([GMAIL_SCOPE])

    with (
        patch(
            "integrations.google.oauth.google.oauth2.credentials.Credentials",
            return_value=valid_creds,
        ),
        patch(
            "integrations.google.oauth.requests.post",
            side_effect=_requests.exceptions.ConnectionError("network unreachable"),
        ),
    ):
        svc = GoogleOAuthService(_make_config(tmp_path))
        with pytest.raises(GoogleOAuthRevokeError) as exc_info:
            await svc.revoke()

    assert exc_info.value.spoken_message
    # Cache file must be removed even when the network call fails
    assert not cache_path.exists()


# ---------------------------------------------------------------------------
# Additional: get_google_oauth_service singleton is stable across calls
# ---------------------------------------------------------------------------


def test_get_google_oauth_service_returns_singleton(tmp_path: Path, monkeypatch: Any) -> None:
    """get_google_oauth_service returns the same instance on repeated calls."""
    import integrations.google.oauth as _mod

    # Reset singleton for isolation
    monkeypatch.setattr(_mod, "_service_instance", None)

    config = _make_config(tmp_path)
    svc_a = get_google_oauth_service(config)
    svc_b = get_google_oauth_service(config)
    assert svc_a is svc_b
