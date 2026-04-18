"""Unit tests for integrations.spotify.client.SpotifyClient.

All spotipy calls are mocked — no network access, no real credentials.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_config(token_cache: str = "/tmp/test_spotify_token.json") -> dict[str, Any]:
    """Return a minimal spotify config dict."""
    return {
        "enabled": True,
        "poll_interval": 10,
        "token_cache_path": token_cache,
        "scopes": [
            "user-read-playback-state",
            "user-modify-playback-state",
            "user-read-currently-playing",
        ],
    }


def _make_playback_data(is_playing: bool = True) -> dict[str, Any]:
    """Return a minimal Spotify current_playback() response dict."""
    return {
        "is_playing": is_playing,
        "progress_ms": 45000,
        "repeat_state": "off",
        "shuffle_state": False,
        "device": {"name": "JARVIS-Desktop", "id": "abc123"},
        "item": {
            "id": "track_001",
            "name": "Bohemian Rhapsody",
            "duration_ms": 354000,
            "artists": [{"name": "Queen"}],
            "album": {
                "name": "A Night at the Opera",
                "images": [{"url": "https://cdn.spotify.com/art.jpg"}],
            },
        },
    }


# ---------------------------------------------------------------------------
# initialize() — happy path (valid cached token)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_initialize_with_valid_cached_token():
    """initialize() completes without raising when a cached token is found."""
    from integrations.spotify.client import SpotifyClient

    cfg = _make_config()

    mock_pkce = MagicMock()
    mock_pkce.get_cached_token.return_value = {"access_token": "tok", "expires_at": 9999}
    mock_pkce.get_authorize_url.return_value = "https://accounts.spotify.com/authorize"

    mock_spotify = MagicMock()

    with (
        patch.dict("os.environ", {"SPOTIFY_CLIENT_ID": "test-client-id"}),
        patch("integrations.spotify.client.Path.mkdir"),
        patch(
            "integrations.spotify.client.asyncio.to_thread",
            new=AsyncMock(return_value={"access_token": "tok", "expires_at": 9999}),
        ),
        patch("spotipy.oauth2.SpotifyPKCE", return_value=mock_pkce),
        patch("spotipy.Spotify", return_value=mock_spotify),
    ):
        client = SpotifyClient(cfg)
        await client.initialize()

    assert client.is_authenticated() is True


@pytest.mark.asyncio
async def test_initialize_creates_token_cache_dir():
    """initialize() calls mkdir(parents=True, exist_ok=True) on the cache dir."""
    from integrations.spotify.client import SpotifyClient

    cfg = _make_config("/tmp/jarvis_test_dir/token.json")
    mock_pkce = MagicMock()
    mock_pkce.get_cached_token.return_value = {"access_token": "tok"}

    mkdir_calls: list = []

    def _fake_mkdir(**kwargs: Any) -> None:
        mkdir_calls.append(kwargs)

    with (
        patch.dict("os.environ", {"SPOTIFY_CLIENT_ID": "test-client-id"}),
        patch("integrations.spotify.client.Path.mkdir", side_effect=_fake_mkdir),
        patch(
            "integrations.spotify.client.asyncio.to_thread",
            new=AsyncMock(return_value={"access_token": "tok"}),
        ),
        patch("spotipy.oauth2.SpotifyPKCE", return_value=mock_pkce),
        patch("spotipy.Spotify"),
    ):
        client = SpotifyClient(cfg)
        await client.initialize()

    assert any(k.get("parents") is True for k in mkdir_calls)


# ---------------------------------------------------------------------------
# initialize() — no token (raises SpotifyAuthError)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_initialize_no_token_raises_auth_error():
    """initialize() raises SpotifyAuthError when no cached token exists."""
    from integrations.spotify.client import SpotifyAuthError, SpotifyClient

    cfg = _make_config()
    mock_pkce = MagicMock()
    mock_pkce.get_authorize_url.return_value = "https://accounts.spotify.com/authorize?foo"

    with (
        patch("integrations.spotify.client.Path.mkdir"),
        patch(
            "integrations.spotify.client.asyncio.to_thread",
            new=AsyncMock(return_value=None),
        ),
        patch("spotipy.oauth2.SpotifyPKCE", return_value=mock_pkce),
    ):
        client = SpotifyClient(cfg)
        with pytest.raises(SpotifyAuthError):
            await client.initialize()

    assert client.is_authenticated() is False


@pytest.mark.asyncio
async def test_get_auth_url_after_failed_initialize():
    """get_auth_url() returns a non-empty PKCE URL after failed initialize()."""
    from integrations.spotify.client import SpotifyAuthError, SpotifyClient

    cfg = _make_config()
    mock_pkce = MagicMock()
    mock_pkce.get_authorize_url.return_value = "https://accounts.spotify.com/authorize?client_id=x"

    with (
        patch.dict("os.environ", {"SPOTIFY_CLIENT_ID": "test-client-id"}),
        patch("integrations.spotify.client.Path.mkdir"),
        patch(
            "integrations.spotify.client.asyncio.to_thread",
            new=AsyncMock(return_value=None),
        ),
        patch("spotipy.oauth2.SpotifyPKCE", return_value=mock_pkce),
    ):
        client = SpotifyClient(cfg)
        with pytest.raises(SpotifyAuthError):
            await client.initialize()
        # _pkce is set before get_cached_token is called, so get_auth_url() works
        auth_url = client.get_auth_url()
        assert auth_url
        assert "spotify.com" in auth_url


# ---------------------------------------------------------------------------
# get_playback_state() — track playing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_playback_state_with_active_track():
    """get_playback_state() returns a populated SpotifyTrackInfo when a track is playing."""
    from integrations.spotify.client import SpotifyClient, SpotifyTrackInfo

    cfg = _make_config()
    data = _make_playback_data(is_playing=True)

    client = SpotifyClient(cfg)
    client._authenticated = True
    client._spotify = MagicMock()

    with patch(
        "integrations.spotify.client.asyncio.to_thread",
        new=AsyncMock(return_value=data),
    ):
        result = await client.get_playback_state()

    assert isinstance(result, SpotifyTrackInfo)
    assert result.name == "Bohemian Rhapsody"
    assert result.artist == "Queen"
    assert result.album == "A Night at the Opera"
    assert result.album_art_url == "https://cdn.spotify.com/art.jpg"
    assert result.duration_ms == 354000
    assert result.progress_ms == 45000
    assert result.is_playing is True
    assert result.device_name == "JARVIS-Desktop"
    assert result.repeat == "off"
    assert result.shuffle is False


# ---------------------------------------------------------------------------
# get_playback_state() — no active playback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_playback_state_returns_none_when_idle():
    """get_playback_state() returns None when no active playback exists."""
    from integrations.spotify.client import SpotifyClient

    cfg = _make_config()
    client = SpotifyClient(cfg)
    client._authenticated = True
    client._spotify = MagicMock()

    with patch(
        "integrations.spotify.client.asyncio.to_thread",
        new=AsyncMock(return_value=None),
    ):
        result = await client.get_playback_state()

    assert result is None


@pytest.mark.asyncio
async def test_get_playback_state_returns_none_for_empty_item():
    """get_playback_state() returns None when the response has no 'item' field."""
    from integrations.spotify.client import SpotifyClient

    cfg = _make_config()
    client = SpotifyClient(cfg)
    client._authenticated = True
    client._spotify = MagicMock()

    data = {"is_playing": False, "item": None}
    with patch(
        "integrations.spotify.client.asyncio.to_thread",
        new=AsyncMock(return_value=data),
    ):
        result = await client.get_playback_state()

    assert result is None


# ---------------------------------------------------------------------------
# get_playback_state() — asyncio.to_thread wrapping (non-blocking check)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_playback_state_uses_to_thread():
    """get_playback_state() wraps the spotipy call in asyncio.to_thread."""
    from integrations.spotify.client import SpotifyClient

    cfg = _make_config()
    client = SpotifyClient(cfg)
    client._authenticated = True
    client._spotify = MagicMock()

    to_thread_calls: list[Any] = []

    async def _fake_to_thread(fn: Any, *args: Any, **kwargs: Any) -> Any:
        to_thread_calls.append(fn)
        return None

    with patch("integrations.spotify.client.asyncio.to_thread", side_effect=_fake_to_thread):
        await client.get_playback_state()

    assert len(to_thread_calls) >= 1


# ---------------------------------------------------------------------------
# get_playback_state() — network error
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_playback_state_raises_poll_error_on_network_failure():
    """get_playback_state() raises SpotifyPollError on unexpected API errors."""
    import spotipy

    from integrations.spotify.client import SpotifyClient, SpotifyPollError

    cfg = _make_config()
    client = SpotifyClient(cfg)
    client._authenticated = True
    client._spotify = MagicMock()

    with patch(
        "integrations.spotify.client.asyncio.to_thread",
        new=AsyncMock(side_effect=spotipy.SpotifyException(500, -1, "server error")),
    ):
        with pytest.raises(SpotifyPollError):
            await client.get_playback_state()


@pytest.mark.asyncio
async def test_get_playback_state_raises_auth_error_on_401():
    """get_playback_state() raises SpotifyAuthError on 401 and clears authenticated flag."""
    import spotipy

    from integrations.spotify.client import SpotifyAuthError, SpotifyClient

    cfg = _make_config()
    client = SpotifyClient(cfg)
    client._authenticated = True
    client._spotify = MagicMock()

    with patch(
        "integrations.spotify.client.asyncio.to_thread",
        new=AsyncMock(side_effect=spotipy.SpotifyException(401, -1, "Unauthorized")),
    ):
        with pytest.raises(SpotifyAuthError):
            await client.get_playback_state()

    assert client.is_authenticated() is False


# ---------------------------------------------------------------------------
# complete_auth() — happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_complete_auth_sets_authenticated():
    """complete_auth() exchanges the code and marks the client as authenticated."""
    from integrations.spotify.client import SpotifyClient

    cfg = _make_config()

    mock_pkce = MagicMock()

    call_log: list[str] = []

    async def _fake_to_thread(fn: Any, *args: Any, **kwargs: Any) -> Any:
        call_log.append("to_thread")
        return {"access_token": "new_tok"}

    with (
        patch.dict("os.environ", {"SPOTIFY_CLIENT_ID": "test-client-id"}),
        patch("integrations.spotify.client.asyncio.to_thread", side_effect=_fake_to_thread),
        patch("spotipy.Spotify"),
        patch("spotipy.oauth2.SpotifyPKCE", return_value=mock_pkce),
        patch("integrations.spotify.client.Path.mkdir"),
    ):
        client = SpotifyClient(cfg)
        await client.complete_auth("auth_code_abc")

    assert client.is_authenticated() is True
    assert "to_thread" in call_log


@pytest.mark.asyncio
async def test_complete_auth_raises_on_bad_code():
    """complete_auth() raises SpotifyAuthError when the code exchange fails."""
    from integrations.spotify.client import SpotifyAuthError, SpotifyClient

    cfg = _make_config()
    client = SpotifyClient(cfg)
    client._pkce = MagicMock()

    with (
        patch(
            "integrations.spotify.client.asyncio.to_thread",
            new=AsyncMock(side_effect=Exception("invalid code")),
        ),
        patch("integrations.spotify.client.Path.mkdir"),
    ):
        with pytest.raises(SpotifyAuthError):
            await client.complete_auth("bad_code")


# ---------------------------------------------------------------------------
# Playback control methods — smoke tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_play_calls_start_playback():
    """play() calls spotify.start_playback via to_thread."""
    from integrations.spotify.client import SpotifyClient

    cfg = _make_config()
    client = SpotifyClient(cfg)
    client._authenticated = True
    client._spotify = MagicMock()

    called: list[Any] = []

    async def _fake_to_thread(fn: Any, *args: Any, **kwargs: Any) -> Any:
        called.append(fn)
        return None

    with patch("integrations.spotify.client.asyncio.to_thread", side_effect=_fake_to_thread):
        await client.play()

    assert called


@pytest.mark.asyncio
async def test_set_volume_clamps_to_100():
    """set_volume() clamps the value to 0–100 before calling the API."""
    from integrations.spotify.client import SpotifyClient

    cfg = _make_config()
    client = SpotifyClient(cfg)
    client._authenticated = True
    client._spotify = MagicMock()

    volume_called_with: list[int] = []

    async def _fake_to_thread(fn: Any, *args: Any, **kwargs: Any) -> Any:
        # fn is spotify.volume; args[0] is the pct
        volume_called_with.append(args[0] if args else 0)
        return None

    with patch("integrations.spotify.client.asyncio.to_thread", side_effect=_fake_to_thread):
        await client.set_volume(150)  # over 100

    assert volume_called_with == [100]


@pytest.mark.asyncio
async def test_set_volume_clamps_to_zero():
    """set_volume() clamps negative values to 0."""
    from integrations.spotify.client import SpotifyClient

    cfg = _make_config()
    client = SpotifyClient(cfg)
    client._authenticated = True
    client._spotify = MagicMock()

    volume_called_with: list[int] = []

    async def _fake_to_thread(fn: Any, *args: Any, **kwargs: Any) -> Any:
        volume_called_with.append(args[0] if args else 0)
        return None

    with patch("integrations.spotify.client.asyncio.to_thread", side_effect=_fake_to_thread):
        await client.set_volume(-10)  # below 0

    assert volume_called_with == [0]


# ---------------------------------------------------------------------------
# Missing SPOTIFY_CLIENT_ID
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_initialize_missing_client_id_raises():
    """initialize() raises SpotifyAuthError when SPOTIFY_CLIENT_ID env var is absent."""
    from integrations.spotify.client import SpotifyAuthError, SpotifyClient

    cfg = _make_config()

    with patch.dict("os.environ", {"SPOTIFY_CLIENT_ID": ""}, clear=False):
        client = SpotifyClient(cfg)
        with pytest.raises(SpotifyAuthError, match="SPOTIFY_CLIENT_ID"):
            await client.initialize()
