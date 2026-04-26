"""Tests for Spotify WebSocket integration in ws_server.

Covers:
- broadcast_spotify_state payload shape (authenticated + track, unauthenticated)
- spotify_oauth_callback_handler: 200 success, 400 no-code, 400 bad code, 503 no client
- _spotify_state_loop broadcasts correct shape on each tick
- _handle_spotify_cmd: all actions dispatched, unknown action logged
- SpotifyAuthError branch in start_ws_server: source-inspection + behaviour guards
"""

from __future__ import annotations

import asyncio
import inspect
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_track_info(**kwargs: Any) -> Any:
    """Return a minimal SpotifyTrackInfo dataclass instance."""
    from integrations.spotify.client import SpotifyTrackInfo

    defaults = {
        "track_id": "t1",
        "name": "Test Song",
        "artist": "Test Artist",
        "album": "Test Album",
        "album_art_url": "https://cdn.spotify.com/art.jpg",
        "duration_ms": 200000,
        "progress_ms": 60000,
        "is_playing": True,
        "shuffle": False,
        "repeat": "off",
        "device_name": "Test Device",
    }
    defaults.update(kwargs)
    return SpotifyTrackInfo(**defaults)


# ---------------------------------------------------------------------------
# broadcast_spotify_state — payload shapes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_broadcast_spotify_state_with_track():
    """broadcast_spotify_state with a track sends a correctly shaped spotify_state frame."""
    sent: list[str] = []

    async def _fake_broadcast(msg: str) -> None:
        sent.append(msg)

    track = _make_track_info()

    with patch("api.ws_server._broadcast", side_effect=_fake_broadcast):
        from api.ws_server import broadcast_spotify_state

        await broadcast_spotify_state(authenticated=True, track=track)

    assert len(sent) == 1
    payload = json.loads(sent[0])
    assert payload["type"] == "spotify_state"
    p = payload["payload"]
    assert p["authenticated"] is True
    assert p["playing"] is True
    assert p["title"] == "Test Song"
    assert p["artist"] == "Test Artist"
    assert p["album"] == "Test Album"
    assert p["album_art_url"] == "https://cdn.spotify.com/art.jpg"
    assert p["progress_ms"] == 60000
    assert p["duration_ms"] == 200000
    assert p["shuffle"] is False
    assert p["repeat"] == "off"
    assert p["device"] == "Test Device"


@pytest.mark.asyncio
async def test_broadcast_spotify_state_without_track():
    """broadcast_spotify_state with no track sends authenticated=False frame."""
    sent: list[str] = []

    async def _fake_broadcast(msg: str) -> None:
        sent.append(msg)

    with patch("api.ws_server._broadcast", side_effect=_fake_broadcast):
        from api.ws_server import broadcast_spotify_state

        await broadcast_spotify_state(authenticated=False)

    assert len(sent) == 1
    payload = json.loads(sent[0])
    assert payload["type"] == "spotify_state"
    p = payload["payload"]
    assert p["authenticated"] is False
    assert p["playing"] is False
    assert p["title"] == ""


@pytest.mark.asyncio
async def test_broadcast_spotify_state_omits_album_art_when_empty():
    """broadcast_spotify_state omits album_art_url key when the URL is empty."""
    sent: list[str] = []

    async def _fake_broadcast(msg: str) -> None:
        sent.append(msg)

    track = _make_track_info(album_art_url="")

    with patch("api.ws_server._broadcast", side_effect=_fake_broadcast):
        from api.ws_server import broadcast_spotify_state

        await broadcast_spotify_state(authenticated=True, track=track)

    assert len(sent) == 1
    payload = json.loads(sent[0])
    # album_art_url should be absent (not an empty string key) when art is empty
    assert "album_art_url" not in payload["payload"]


# ---------------------------------------------------------------------------
# spotify_oauth_callback_handler — 200 success
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_oauth_callback_success_returns_200():
    """GET /oauth/spotify/callback?code=abc returns 200 HTML containing 'Spotify connected'."""
    import api.ws_server as srv

    mock_client = MagicMock()
    mock_client.complete_auth = AsyncMock()
    mock_client.is_authenticated.return_value = True

    # Inject client so the handler finds it.
    orig = srv._spotify_client
    srv._spotify_client = mock_client

    try:
        request = MagicMock()
        request.rel_url.query.get.return_value = "valid_code"

        mock_cfg = MagicMock()
        mock_cfg.get_section.return_value = {"poll_interval": 10}

        with (
            patch("api.ws_server.broadcast_notification", new_callable=AsyncMock),
            patch("api.ws_server.asyncio.create_task"),
            # The handler does a local import: from utils.config_loader import get_config
            patch("utils.config_loader.get_config", return_value=mock_cfg),
        ):
            from api.ws_server import spotify_oauth_callback_handler

            response = await spotify_oauth_callback_handler(request)

        assert response.status == 200
        assert "Spotify connected" in response.text
    finally:
        srv._spotify_client = orig


@pytest.mark.asyncio
async def test_oauth_callback_missing_code_returns_400():
    """GET /oauth/spotify/callback with no code returns 400."""
    from api.ws_server import spotify_oauth_callback_handler

    request = MagicMock()
    request.rel_url.query.get.return_value = None  # no code

    response = await spotify_oauth_callback_handler(request)
    assert response.status == 400
    assert "Authorization failed" in response.text


@pytest.mark.asyncio
async def test_oauth_callback_no_client_returns_503():
    """GET /oauth/spotify/callback returns 503 when SpotifyClient is not initialised."""
    import api.ws_server as srv

    orig = srv._spotify_client
    srv._spotify_client = None

    try:
        request = MagicMock()
        request.rel_url.query.get.return_value = "some_code"

        from api.ws_server import spotify_oauth_callback_handler

        response = await spotify_oauth_callback_handler(request)
        assert response.status == 503
        assert "not ready" in response.text.lower()
    finally:
        srv._spotify_client = orig


@pytest.mark.asyncio
async def test_oauth_callback_bad_code_returns_400():
    """GET /oauth/spotify/callback with an already-consumed code returns 400."""
    import api.ws_server as srv
    from integrations.spotify.client import SpotifyAuthError

    mock_client = MagicMock()
    mock_client.complete_auth = AsyncMock(
        side_effect=SpotifyAuthError("code expired or already used")
    )

    orig = srv._spotify_client
    srv._spotify_client = mock_client

    try:
        request = MagicMock()
        request.rel_url.query.get.return_value = "bad_code"

        from api.ws_server import spotify_oauth_callback_handler

        response = await spotify_oauth_callback_handler(request)
        assert response.status == 400
        assert "expired or already used" in response.text.lower()
    finally:
        srv._spotify_client = orig


# ---------------------------------------------------------------------------
# _spotify_state_loop — broadcast shape
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_spotify_state_loop_broadcasts_on_each_tick():
    """_spotify_state_loop broadcasts a spotify_state frame on each tick.

    The loop sleeps before polling, so we make asyncio.sleep a no-op and
    run several event-loop iterations to let the broadcast happen.
    """
    from api.ws_server import _spotify_state_loop

    mock_client = MagicMock()
    mock_client.is_authenticated.return_value = True
    mock_client.get_playback_state = AsyncMock(return_value=_make_track_info())

    broadcast_calls: list[Any] = []
    sleep_call_count = 0

    async def _fake_broadcast_spotify_state(**kwargs: Any) -> None:
        broadcast_calls.append(kwargs)

    async def _instant_sleep(seconds: float) -> None:
        nonlocal sleep_call_count
        sleep_call_count += 1
        # After 2 sleeps (enough for one full iteration), cancel via CancelledError
        if sleep_call_count >= 2:
            raise asyncio.CancelledError

    with (
        patch("api.ws_server.broadcast_spotify_state", side_effect=_fake_broadcast_spotify_state),
        patch("api.ws_server.asyncio.sleep", side_effect=_instant_sleep),
    ):
        task = asyncio.create_task(_spotify_state_loop(mock_client, interval_seconds=1))
        try:
            await task
        except asyncio.CancelledError:
            pass

    assert len(broadcast_calls) >= 1
    # The broadcast must include at least authenticated=True
    assert broadcast_calls[0]["authenticated"] is True


@pytest.mark.asyncio
async def test_spotify_state_loop_broadcasts_unauthenticated_on_auth_error():
    """_spotify_state_loop broadcasts authenticated=False on SpotifyAuthError."""
    from api.ws_server import _spotify_state_loop
    from integrations.spotify.client import SpotifyAuthError

    mock_client = MagicMock()
    mock_client.is_authenticated.return_value = True
    mock_client.get_playback_state = AsyncMock(
        side_effect=SpotifyAuthError("token revoked")
    )

    unauthenticated_calls: list[bool] = []
    sleep_call_count = 0

    async def _fake_broadcast(authenticated: bool = True, **kwargs: Any) -> None:
        unauthenticated_calls.append(authenticated)

    async def _instant_sleep(seconds: float) -> None:
        nonlocal sleep_call_count
        sleep_call_count += 1
        if sleep_call_count >= 2:
            raise asyncio.CancelledError

    with (
        patch("api.ws_server.broadcast_spotify_state", side_effect=_fake_broadcast),
        patch("api.ws_server.asyncio.sleep", side_effect=_instant_sleep),
    ):
        task = asyncio.create_task(_spotify_state_loop(mock_client, interval_seconds=1))
        try:
            await task
        except asyncio.CancelledError:
            pass

    assert any(v is False for v in unauthenticated_calls)


# ---------------------------------------------------------------------------
# _handle_spotify_cmd — dispatches actions + logs unknown
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_spotify_cmd_play_calls_client_play():
    """_handle_spotify_cmd with action='play' calls client.play()."""
    import api.ws_server as srv

    mock_client = MagicMock()
    mock_client.is_authenticated.return_value = True
    mock_client.play = AsyncMock()

    orig = srv._spotify_client
    srv._spotify_client = mock_client

    try:
        from api.ws_server import _handle_spotify_cmd

        await _handle_spotify_cmd({"action": "play"})
        mock_client.play.assert_awaited_once()
    finally:
        srv._spotify_client = orig


@pytest.mark.asyncio
async def test_spotify_cmd_pause_calls_client_pause():
    """_handle_spotify_cmd with action='pause' calls client.pause()."""
    import api.ws_server as srv

    mock_client = MagicMock()
    mock_client.is_authenticated.return_value = True
    mock_client.pause = AsyncMock()

    orig = srv._spotify_client
    srv._spotify_client = mock_client

    try:
        from api.ws_server import _handle_spotify_cmd

        await _handle_spotify_cmd({"action": "pause"})
        mock_client.pause.assert_awaited_once()
    finally:
        srv._spotify_client = orig


@pytest.mark.asyncio
async def test_spotify_cmd_next_calls_next_track():
    """_handle_spotify_cmd with action='next' calls client.next_track()."""
    import api.ws_server as srv

    mock_client = MagicMock()
    mock_client.is_authenticated.return_value = True
    mock_client.next_track = AsyncMock()

    orig = srv._spotify_client
    srv._spotify_client = mock_client

    try:
        from api.ws_server import _handle_spotify_cmd

        await _handle_spotify_cmd({"action": "next"})
        mock_client.next_track.assert_awaited_once()
    finally:
        srv._spotify_client = orig


@pytest.mark.asyncio
async def test_spotify_cmd_prev_calls_previous_track():
    """_handle_spotify_cmd with action='prev' calls client.previous_track()."""
    import api.ws_server as srv

    mock_client = MagicMock()
    mock_client.is_authenticated.return_value = True
    mock_client.previous_track = AsyncMock()

    orig = srv._spotify_client
    srv._spotify_client = mock_client

    try:
        from api.ws_server import _handle_spotify_cmd

        await _handle_spotify_cmd({"action": "prev"})
        mock_client.previous_track.assert_awaited_once()
    finally:
        srv._spotify_client = orig


@pytest.mark.asyncio
async def test_spotify_cmd_volume_calls_set_volume():
    """_handle_spotify_cmd with action='volume' and value=75 calls client.set_volume(75)."""
    import api.ws_server as srv

    mock_client = MagicMock()
    mock_client.is_authenticated.return_value = True
    mock_client.set_volume = AsyncMock()

    orig = srv._spotify_client
    srv._spotify_client = mock_client

    try:
        from api.ws_server import _handle_spotify_cmd

        await _handle_spotify_cmd({"action": "volume", "value": 75})
        mock_client.set_volume.assert_awaited_once_with(75)
    finally:
        srv._spotify_client = orig


@pytest.mark.asyncio
async def test_spotify_cmd_unknown_action_does_not_raise():
    """_handle_spotify_cmd with an unknown action logs a warning and does not raise."""
    import api.ws_server as srv

    mock_client = MagicMock()
    mock_client.is_authenticated.return_value = True

    orig = srv._spotify_client
    srv._spotify_client = mock_client

    try:
        from api.ws_server import _handle_spotify_cmd

        # Must not raise
        await _handle_spotify_cmd({"action": "shuffle_toggle"})
    finally:
        srv._spotify_client = orig


@pytest.mark.asyncio
async def test_spotify_cmd_no_client_does_not_raise():
    """_handle_spotify_cmd does nothing when _spotify_client is None."""
    import api.ws_server as srv

    orig = srv._spotify_client
    srv._spotify_client = None

    try:
        from api.ws_server import _handle_spotify_cmd

        await _handle_spotify_cmd({"action": "play"})
        # Should complete without error
    finally:
        srv._spotify_client = orig


@pytest.mark.asyncio
async def test_spotify_cmd_unauthenticated_does_not_call_client():
    """_handle_spotify_cmd ignores the command when the client is not authenticated."""
    import api.ws_server as srv

    mock_client = MagicMock()
    mock_client.is_authenticated.return_value = False
    mock_client.play = AsyncMock()

    orig = srv._spotify_client
    srv._spotify_client = mock_client

    try:
        from api.ws_server import _handle_spotify_cmd

        await _handle_spotify_cmd({"action": "play"})
        mock_client.play.assert_not_awaited()
    finally:
        srv._spotify_client = orig


# ---------------------------------------------------------------------------
# SpotifyAuthError branch in start_ws_server — source-inspection guards
# ---------------------------------------------------------------------------


def _start_ws_server_source() -> str:
    """Return the source of start_ws_server (cached per process)."""
    import api.ws_server as ws

    return inspect.getsource(ws.start_ws_server)


def test_auth_error_branch_broadcasts_unauthenticated_state():
    """start_ws_server SpotifyAuthError branch must call broadcast_spotify_state(authenticated=False."""
    src = _start_ws_server_source()
    assert "broadcast_spotify_state(authenticated=False" in src, (
        "SpotifyAuthError branch must immediately broadcast authenticated=False "
        "so the HUD renders AuthPrompt instead of the no-playback fallback."
    )


def test_auth_error_branch_starts_state_loop():
    """start_ws_server SpotifyAuthError branch must start _spotify_state_loop."""
    src = _start_ws_server_source()
    # The substring must appear in the except-SpotifyAuthError block; verify it
    # occurs *after* the SpotifyAuthError catch line in the source.
    auth_err_pos = src.find("except SpotifyAuthError")
    loop_pos = src.find("_spotify_state_loop(_spotify_client", auth_err_pos)
    assert auth_err_pos != -1, "SpotifyAuthError branch not found in start_ws_server"
    assert loop_pos != -1, (
        "_spotify_state_loop(_spotify_client must be started inside the "
        "SpotifyAuthError branch so the HUD keeps receiving auth-state updates."
    )


def test_auth_error_branch_wires_orchestrator():
    """start_ws_server SpotifyAuthError branch must wire the client into the orchestrator."""
    src = _start_ws_server_source()
    auth_err_pos = src.find("except SpotifyAuthError")
    orch_pos = src.find("_orchestrator.set_spotify_client(_spotify_client)", auth_err_pos)
    assert auth_err_pos != -1, "SpotifyAuthError branch not found in start_ws_server"
    assert orch_pos != -1, (
        "_orchestrator.set_spotify_client(_spotify_client) must be called inside "
        "the SpotifyAuthError branch so voice intents return a proper spoken response."
    )
