"""Unit tests for SpotifyClient — new methods added in issue #58.

Covers all 10 new library/search/queue/play methods.
All spotipy calls are mocked at the module boundary — no network access.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest
import spotipy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config() -> dict[str, Any]:
    return {
        "enabled": True,
        "poll_interval": 10,
        "token_cache_path": "/tmp/test_token.json",
        "scopes": [
            "user-read-playback-state",
            "user-modify-playback-state",
            "playlist-read-private",
            "playlist-read-collaborative",
            "user-library-read",
        ],
    }


def _make_client(authenticated: bool = True) -> Any:
    """Return a SpotifyClient with _spotify pre-wired."""
    from integrations.spotify.client import SpotifyClient

    client = SpotifyClient(_make_config())
    if authenticated:
        client._spotify = MagicMock()
        client._authenticated = True
    return client


def _spotify_exc(status: int) -> spotipy.SpotifyException:
    """Build a SpotifyException with the given http_status."""
    exc = spotipy.SpotifyException(status, -1, "mock error")
    exc.http_status = status
    return exc


def _rate_limited_exc(retry_after: int = 5) -> spotipy.SpotifyException:
    exc = _spotify_exc(429)
    exc.headers = {"Retry-After": str(retry_after)}
    return exc


# ---------------------------------------------------------------------------
# list_playlists
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_playlists_happy_path_returns_dataclasses():
    """list_playlists() maps the spotipy response to SpotifyPlaylist dataclasses."""
    from integrations.spotify.client import SpotifyClient, SpotifyPlaylist

    client = _make_client()
    spotipy_response = {
        "items": [
            {
                "id": "pl1",
                "name": "Coding Sessions",
                "owner": {"display_name": "user1"},
                "tracks": {"total": 42},
                "uri": "spotify:playlist:pl1",
            }
        ]
    }

    with patch(
        "integrations.spotify.client.asyncio.to_thread",
        new=AsyncMock(return_value=spotipy_response),
    ):
        result = await client.list_playlists()

    assert len(result) == 1
    pl = result[0]
    assert isinstance(pl, SpotifyPlaylist)
    assert pl.id == "pl1"
    assert pl.name == "Coding Sessions"
    assert pl.owner == "user1"
    assert pl.track_count == 42
    assert pl.uri == "spotify:playlist:pl1"


@pytest.mark.asyncio
async def test_list_playlists_passes_limit_and_offset():
    """list_playlists(limit=50, offset=50) passes those params to spotipy."""
    from integrations.spotify.client import SpotifyClient

    client = _make_client()
    captured: list[dict] = []

    async def _fake(fn: Any, **kwargs: Any) -> dict:
        captured.append(kwargs)
        return {"items": []}

    with patch("integrations.spotify.client.asyncio.to_thread", side_effect=_fake):
        await client.list_playlists(limit=50, offset=50)

    assert captured[0]["limit"] == 50
    assert captured[0]["offset"] == 50


@pytest.mark.asyncio
async def test_list_playlists_skips_none_items():
    """list_playlists() silently skips None entries in the API response."""
    from integrations.spotify.client import SpotifyClient

    client = _make_client()
    response = {"items": [None, {"id": "pl2", "name": "X", "owner": {"display_name": "u"}, "tracks": {"total": 1}, "uri": "u:pl2"}]}

    with patch("integrations.spotify.client.asyncio.to_thread", new=AsyncMock(return_value=response)):
        result = await client.list_playlists()

    assert len(result) == 1


@pytest.mark.asyncio
async def test_list_playlists_raises_auth_error_when_not_authenticated():
    """list_playlists() raises SpotifyAuthError when _spotify is None."""
    from integrations.spotify.client import SpotifyAuthError, SpotifyClient

    client = SpotifyClient(_make_config())  # _spotify is None

    with pytest.raises(SpotifyAuthError):
        await client.list_playlists()


@pytest.mark.asyncio
async def test_list_playlists_raises_on_401():
    """list_playlists() raises SpotifyAuthError on 401 from spotipy."""
    from integrations.spotify.client import SpotifyAuthError

    client = _make_client()

    with patch(
        "integrations.spotify.client.asyncio.to_thread",
        new=AsyncMock(side_effect=_spotify_exc(401)),
    ):
        with pytest.raises(SpotifyAuthError):
            await client.list_playlists()


@pytest.mark.asyncio
async def test_list_playlists_raises_premium_error_on_403():
    """list_playlists() raises SpotifyPremiumError on 403."""
    from integrations.spotify.client import SpotifyPremiumError

    client = _make_client()

    with patch(
        "integrations.spotify.client.asyncio.to_thread",
        new=AsyncMock(side_effect=_spotify_exc(403)),
    ):
        with pytest.raises(SpotifyPremiumError):
            await client.list_playlists()


@pytest.mark.asyncio
async def test_list_playlists_raises_poll_error_on_429():
    """list_playlists() raises SpotifyPollError on 429 and captures retry_after."""
    from integrations.spotify.client import SpotifyPollError

    client = _make_client()

    with patch(
        "integrations.spotify.client.asyncio.to_thread",
        new=AsyncMock(side_effect=_rate_limited_exc(10)),
    ):
        with pytest.raises(SpotifyPollError) as exc_info:
            await client.list_playlists()

    assert exc_info.value.retry_after == "10"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# playlist_tracks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_playlist_tracks_happy_path():
    """playlist_tracks() returns SpotifyTrackResult list from wrapped track items."""
    from integrations.spotify.client import SpotifyTrackResult

    client = _make_client()
    response = {
        "items": [
            {
                "track": {
                    "id": "t1",
                    "name": "Midnight City",
                    "artists": [{"name": "M83"}],
                    "album": {"name": "Hurry Up"},
                    "duration_ms": 241000,
                    "uri": "spotify:track:t1",
                }
            }
        ]
    }

    with patch("integrations.spotify.client.asyncio.to_thread", new=AsyncMock(return_value=response)):
        result = await client.playlist_tracks("pl1")

    assert len(result) == 1
    assert isinstance(result[0], SpotifyTrackResult)
    assert result[0].name == "Midnight City"
    assert result[0].artist == "M83"


@pytest.mark.asyncio
async def test_playlist_tracks_raises_auth_error_when_none():
    """playlist_tracks() raises SpotifyAuthError when _spotify is None."""
    from integrations.spotify.client import SpotifyAuthError, SpotifyClient

    client = SpotifyClient(_make_config())
    with pytest.raises(SpotifyAuthError):
        await client.playlist_tracks("pl1")


@pytest.mark.asyncio
async def test_playlist_tracks_raises_premium_error_on_403():
    """playlist_tracks() raises SpotifyPremiumError on 403."""
    from integrations.spotify.client import SpotifyPremiumError

    client = _make_client()
    with patch("integrations.spotify.client.asyncio.to_thread", new=AsyncMock(side_effect=_spotify_exc(403))):
        with pytest.raises(SpotifyPremiumError):
            await client.playlist_tracks("pl1")


# ---------------------------------------------------------------------------
# album_tracks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_album_tracks_happy_path():
    """album_tracks() returns SpotifyTrackResult list without album field."""
    from integrations.spotify.client import SpotifyTrackResult

    client = _make_client()
    response = {
        "items": [
            {
                "id": "t2",
                "name": "Intro",
                "artists": [{"name": "The xx"}],
                "duration_ms": 130000,
                "uri": "spotify:track:t2",
            }
        ]
    }

    with patch("integrations.spotify.client.asyncio.to_thread", new=AsyncMock(return_value=response)):
        result = await client.album_tracks("al1")

    assert len(result) == 1
    assert isinstance(result[0], SpotifyTrackResult)
    assert result[0].name == "Intro"
    assert result[0].artist == "The xx"
    assert result[0].album == ""  # album_tracks endpoint does not set album name per track


@pytest.mark.asyncio
async def test_album_tracks_raises_auth_error_when_none():
    """album_tracks() raises SpotifyAuthError when _spotify is None."""
    from integrations.spotify.client import SpotifyAuthError, SpotifyClient

    client = SpotifyClient(_make_config())
    with pytest.raises(SpotifyAuthError):
        await client.album_tracks("al1")


@pytest.mark.asyncio
async def test_album_tracks_raises_on_401():
    """album_tracks() raises SpotifyAuthError on 401."""
    from integrations.spotify.client import SpotifyAuthError

    client = _make_client()
    with patch("integrations.spotify.client.asyncio.to_thread", new=AsyncMock(side_effect=_spotify_exc(401))):
        with pytest.raises(SpotifyAuthError):
            await client.album_tracks("al1")


# ---------------------------------------------------------------------------
# saved_tracks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_saved_tracks_happy_path():
    """saved_tracks() maps saved_tracks API response to SpotifyTrackResult list."""
    from integrations.spotify.client import SpotifyTrackResult

    client = _make_client()
    response = {
        "items": [
            {
                "track": {
                    "id": "t3",
                    "name": "Oblivion",
                    "artists": [{"name": "Grimes"}],
                    "album": {"name": "Visions"},
                    "duration_ms": 253000,
                    "uri": "spotify:track:t3",
                }
            }
        ]
    }

    with patch("integrations.spotify.client.asyncio.to_thread", new=AsyncMock(return_value=response)):
        result = await client.saved_tracks()

    assert len(result) == 1
    assert isinstance(result[0], SpotifyTrackResult)
    assert result[0].name == "Oblivion"


@pytest.mark.asyncio
async def test_saved_tracks_raises_auth_error_when_none():
    """saved_tracks() raises SpotifyAuthError when _spotify is None."""
    from integrations.spotify.client import SpotifyAuthError, SpotifyClient

    client = SpotifyClient(_make_config())
    with pytest.raises(SpotifyAuthError):
        await client.saved_tracks()


@pytest.mark.asyncio
async def test_saved_tracks_raises_poll_error_on_429():
    """saved_tracks() raises SpotifyPollError on 429."""
    from integrations.spotify.client import SpotifyPollError

    client = _make_client()
    with patch("integrations.spotify.client.asyncio.to_thread", new=AsyncMock(side_effect=_spotify_exc(429))):
        with pytest.raises(SpotifyPollError):
            await client.saved_tracks()


# ---------------------------------------------------------------------------
# saved_albums
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_saved_albums_happy_path():
    """saved_albums() returns raw album dicts with expected keys."""
    client = _make_client()
    response = {
        "items": [
            {
                "album": {
                    "id": "al1",
                    "name": "Visions",
                    "artists": [{"name": "Grimes"}],
                    "total_tracks": 14,
                    "uri": "spotify:album:al1",
                    "release_date": "2012-01-01",
                }
            }
        ]
    }

    with patch("integrations.spotify.client.asyncio.to_thread", new=AsyncMock(return_value=response)):
        result = await client.saved_albums()

    assert len(result) == 1
    al = result[0]
    assert al["id"] == "al1"
    assert al["name"] == "Visions"
    assert al["artist"] == "Grimes"
    assert al["total_tracks"] == 14
    assert al["uri"] == "spotify:album:al1"
    assert al["release_date"] == "2012-01-01"


@pytest.mark.asyncio
async def test_saved_albums_raises_auth_error_when_none():
    """saved_albums() raises SpotifyAuthError when _spotify is None."""
    from integrations.spotify.client import SpotifyAuthError, SpotifyClient

    client = SpotifyClient(_make_config())
    with pytest.raises(SpotifyAuthError):
        await client.saved_albums()


@pytest.mark.asyncio
async def test_saved_albums_raises_premium_error_on_403():
    """saved_albums() raises SpotifyPremiumError on 403."""
    from integrations.spotify.client import SpotifyPremiumError

    client = _make_client()
    with patch("integrations.spotify.client.asyncio.to_thread", new=AsyncMock(side_effect=_spotify_exc(403))):
        with pytest.raises(SpotifyPremiumError):
            await client.saved_albums()


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_happy_path_returns_all_buckets():
    """search() returns SpotifySearchResults with tracks, artists, albums, playlists."""
    from integrations.spotify.client import SpotifySearchResults, SpotifyTrackResult, SpotifyPlaylist

    client = _make_client()
    response = {
        "tracks": {
            "items": [
                {
                    "id": "t1",
                    "name": "Song",
                    "artists": [{"name": "Artist"}],
                    "album": {"name": "Album"},
                    "duration_ms": 200000,
                    "uri": "spotify:track:t1",
                }
            ]
        },
        "artists": {"items": [{"id": "ar1", "name": "Artist", "uri": "spotify:artist:ar1", "genres": ["pop"]}]},
        "albums": {
            "items": [
                {
                    "id": "al1",
                    "name": "Album",
                    "artists": [{"name": "Artist"}],
                    "uri": "spotify:album:al1",
                    "release_date": "2020",
                    "total_tracks": 10,
                }
            ]
        },
        "playlists": {
            "items": [
                {
                    "id": "pl1",
                    "name": "Playlist",
                    "owner": {"display_name": "user"},
                    "tracks": {"total": 5},
                    "uri": "spotify:playlist:pl1",
                }
            ]
        },
    }

    with patch("integrations.spotify.client.asyncio.to_thread", new=AsyncMock(return_value=response)):
        result = await client.search("Song")

    assert isinstance(result, SpotifySearchResults)
    assert len(result.tracks) == 1
    assert isinstance(result.tracks[0], SpotifyTrackResult)
    assert len(result.artists) == 1
    assert result.artists[0]["name"] == "Artist"
    assert len(result.albums) == 1
    assert len(result.playlists) == 1
    assert isinstance(result.playlists[0], SpotifyPlaylist)


@pytest.mark.asyncio
async def test_search_passes_types_as_comma_joined_string():
    """search(types=['track','artist']) passes type='track,artist' to spotipy."""
    client = _make_client()
    captured: list[dict] = []

    async def _fake(fn: Any, q: Any, **kwargs: Any) -> dict:
        captured.append(kwargs)
        return {}

    with patch("integrations.spotify.client.asyncio.to_thread", side_effect=_fake):
        await client.search("test", types=["track", "artist"])

    assert captured[0]["type"] == "track,artist"


@pytest.mark.asyncio
async def test_search_uses_default_types_when_none_provided():
    """search() defaults to all four types when types=None."""
    client = _make_client()
    captured: list[dict] = []

    async def _fake(fn: Any, q: Any, **kwargs: Any) -> dict:
        captured.append(kwargs)
        return {}

    with patch("integrations.spotify.client.asyncio.to_thread", side_effect=_fake):
        await client.search("test")

    assert captured[0]["type"] == "track,artist,album,playlist"


@pytest.mark.asyncio
async def test_search_raises_auth_error_when_none():
    """search() raises SpotifyAuthError when _spotify is None."""
    from integrations.spotify.client import SpotifyAuthError, SpotifyClient

    client = SpotifyClient(_make_config())
    with pytest.raises(SpotifyAuthError):
        await client.search("test")


@pytest.mark.asyncio
async def test_search_raises_premium_error_on_403():
    """search() raises SpotifyPremiumError on 403."""
    from integrations.spotify.client import SpotifyPremiumError

    client = _make_client()
    with patch("integrations.spotify.client.asyncio.to_thread", new=AsyncMock(side_effect=_spotify_exc(403))):
        with pytest.raises(SpotifyPremiumError):
            await client.search("test")


@pytest.mark.asyncio
async def test_search_raises_poll_error_on_429_with_retry_after():
    """search() raises SpotifyPollError with retry_after attribute on 429."""
    from integrations.spotify.client import SpotifyPollError

    client = _make_client()
    with patch("integrations.spotify.client.asyncio.to_thread", new=AsyncMock(side_effect=_rate_limited_exc(30))):
        with pytest.raises(SpotifyPollError) as exc_info:
            await client.search("test")

    assert hasattr(exc_info.value, "retry_after")


@pytest.mark.asyncio
async def test_search_empty_response_returns_empty_buckets():
    """search() returns empty buckets when the API returns None."""
    from integrations.spotify.client import SpotifySearchResults

    client = _make_client()
    with patch("integrations.spotify.client.asyncio.to_thread", new=AsyncMock(return_value=None)):
        result = await client.search("empty")

    assert isinstance(result, SpotifySearchResults)
    assert result.tracks == []
    assert result.artists == []
    assert result.albums == []
    assert result.playlists == []


# ---------------------------------------------------------------------------
# get_queue
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_queue_happy_path():
    """get_queue() returns SpotifyQueueItem list with correct positions."""
    from integrations.spotify.client import SpotifyQueueItem

    client = _make_client()
    response = {
        "queue": [
            {"name": "Oblivion", "artists": [{"name": "Grimes"}], "uri": "spotify:track:t2"},
            {"name": "Intro", "artists": [{"name": "The xx"}], "uri": "spotify:track:t3"},
        ]
    }

    with patch("integrations.spotify.client.asyncio.to_thread", new=AsyncMock(return_value=response)):
        result = await client.get_queue()

    assert len(result) == 2
    assert isinstance(result[0], SpotifyQueueItem)
    assert result[0].position == 0
    assert result[0].name == "Oblivion"
    assert result[1].position == 1
    assert result[1].name == "Intro"


@pytest.mark.asyncio
async def test_get_queue_raises_auth_error_when_none():
    """get_queue() raises SpotifyAuthError when _spotify is None."""
    from integrations.spotify.client import SpotifyAuthError, SpotifyClient

    client = SpotifyClient(_make_config())
    with pytest.raises(SpotifyAuthError):
        await client.get_queue()


@pytest.mark.asyncio
async def test_get_queue_raises_premium_error_on_403():
    """get_queue() raises SpotifyPremiumError on 403."""
    from integrations.spotify.client import SpotifyPremiumError

    client = _make_client()
    with patch("integrations.spotify.client.asyncio.to_thread", new=AsyncMock(side_effect=_spotify_exc(403))):
        with pytest.raises(SpotifyPremiumError):
            await client.get_queue()


@pytest.mark.asyncio
async def test_get_queue_skips_none_items():
    """get_queue() silently skips None entries."""
    client = _make_client()
    response = {"queue": [None, {"name": "Song", "artists": [{"name": "A"}], "uri": "spotify:track:t1"}]}

    with patch("integrations.spotify.client.asyncio.to_thread", new=AsyncMock(return_value=response)):
        result = await client.get_queue()

    assert len(result) == 1
    assert result[0].position == 1  # none was at index 0, "Song" is at index 1


# ---------------------------------------------------------------------------
# add_to_queue
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_to_queue_calls_spotipy_add_to_queue():
    """add_to_queue() calls spotify.add_to_queue via to_thread with the URI."""
    client = _make_client()
    captured: list[tuple] = []

    async def _fake(fn: Any, *args: Any, **kwargs: Any) -> None:
        captured.append((fn, args, kwargs))

    with patch("integrations.spotify.client.asyncio.to_thread", side_effect=_fake):
        await client.add_to_queue("spotify:track:abc")

    assert len(captured) == 1
    fn, args, _ = captured[0]
    assert fn == client._spotify.add_to_queue
    assert args == ("spotify:track:abc",)


@pytest.mark.asyncio
async def test_add_to_queue_raises_auth_error_when_none():
    """add_to_queue() raises SpotifyAuthError when _spotify is None."""
    from integrations.spotify.client import SpotifyAuthError, SpotifyClient

    client = SpotifyClient(_make_config())
    with pytest.raises(SpotifyAuthError):
        await client.add_to_queue("spotify:track:abc")


@pytest.mark.asyncio
async def test_add_to_queue_raises_premium_error_on_403():
    """add_to_queue() raises SpotifyPremiumError on 403."""
    from integrations.spotify.client import SpotifyPremiumError

    client = _make_client()
    with patch("integrations.spotify.client.asyncio.to_thread", new=AsyncMock(side_effect=_spotify_exc(403))):
        with pytest.raises(SpotifyPremiumError):
            await client.add_to_queue("spotify:track:abc")


# ---------------------------------------------------------------------------
# play_context
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_play_context_calls_start_playback_with_context_uri():
    """play_context() calls spotify.start_playback(context_uri=...) via to_thread."""
    client = _make_client()
    captured: list[dict] = []

    async def _fake(fn: Any, **kwargs: Any) -> None:
        captured.append(kwargs)

    with patch("integrations.spotify.client.asyncio.to_thread", side_effect=_fake):
        await client.play_context("spotify:playlist:pl1")

    assert captured[0]["context_uri"] == "spotify:playlist:pl1"
    assert "offset" not in captured[0]


@pytest.mark.asyncio
async def test_play_context_passes_offset_when_provided():
    """play_context(context_uri, offset_uri) passes offset dict to spotipy."""
    client = _make_client()
    captured: list[dict] = []

    async def _fake(fn: Any, **kwargs: Any) -> None:
        captured.append(kwargs)

    with patch("integrations.spotify.client.asyncio.to_thread", side_effect=_fake):
        await client.play_context("spotify:playlist:pl1", offset_uri="spotify:track:t1")

    assert captured[0]["offset"] == {"uri": "spotify:track:t1"}


@pytest.mark.asyncio
async def test_play_context_raises_auth_error_when_none():
    """play_context() raises SpotifyAuthError when _spotify is None."""
    from integrations.spotify.client import SpotifyAuthError, SpotifyClient

    client = SpotifyClient(_make_config())
    with pytest.raises(SpotifyAuthError):
        await client.play_context("spotify:playlist:pl1")


@pytest.mark.asyncio
async def test_play_context_raises_premium_error_on_403():
    """play_context() raises SpotifyPremiumError on 403."""
    from integrations.spotify.client import SpotifyPremiumError

    client = _make_client()
    with patch("integrations.spotify.client.asyncio.to_thread", new=AsyncMock(side_effect=_spotify_exc(403))):
        with pytest.raises(SpotifyPremiumError):
            await client.play_context("spotify:playlist:pl1")


# ---------------------------------------------------------------------------
# play_uris
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_play_uris_calls_start_playback_with_uris():
    """play_uris() calls spotify.start_playback(uris=[...]) via to_thread."""
    client = _make_client()
    captured: list[dict] = []

    async def _fake(fn: Any, **kwargs: Any) -> None:
        captured.append(kwargs)

    with patch("integrations.spotify.client.asyncio.to_thread", side_effect=_fake):
        await client.play_uris(["spotify:track:t1", "spotify:track:t2"])

    assert captured[0]["uris"] == ["spotify:track:t1", "spotify:track:t2"]


@pytest.mark.asyncio
async def test_play_uris_empty_list_is_noop():
    """play_uris([]) returns without calling spotipy (logged warning only)."""
    client = _make_client()
    called: list = []

    async def _fake(fn: Any, **kwargs: Any) -> None:
        called.append(fn)

    with patch("integrations.spotify.client.asyncio.to_thread", side_effect=_fake):
        await client.play_uris([])

    assert called == []


@pytest.mark.asyncio
async def test_play_uris_raises_auth_error_when_none():
    """play_uris() raises SpotifyAuthError when _spotify is None."""
    from integrations.spotify.client import SpotifyAuthError, SpotifyClient

    client = SpotifyClient(_make_config())
    with pytest.raises(SpotifyAuthError):
        await client.play_uris(["spotify:track:t1"])


@pytest.mark.asyncio
async def test_play_uris_raises_premium_error_on_403():
    """play_uris() raises SpotifyPremiumError on 403."""
    from integrations.spotify.client import SpotifyPremiumError

    client = _make_client()
    with patch("integrations.spotify.client.asyncio.to_thread", new=AsyncMock(side_effect=_spotify_exc(403))):
        with pytest.raises(SpotifyPremiumError):
            await client.play_uris(["spotify:track:t1"])


# ---------------------------------------------------------------------------
# _map_spotipy_exception — direct unit tests
# ---------------------------------------------------------------------------


def test_map_spotipy_exception_401_returns_auth_error_and_resets_flag():
    """_map_spotipy_exception(401) returns SpotifyAuthError and marks unauthenticated."""
    from integrations.spotify.client import SpotifyAuthError

    client = _make_client()
    result = client._map_spotipy_exception(_spotify_exc(401))
    assert isinstance(result, SpotifyAuthError)
    assert client._authenticated is False


def test_map_spotipy_exception_403_returns_premium_error():
    """_map_spotipy_exception(403) returns SpotifyPremiumError."""
    from integrations.spotify.client import SpotifyPremiumError

    client = _make_client()
    result = client._map_spotipy_exception(_spotify_exc(403))
    assert isinstance(result, SpotifyPremiumError)


def test_map_spotipy_exception_429_attaches_retry_after():
    """_map_spotipy_exception(429 + headers) attaches retry_after."""
    from integrations.spotify.client import SpotifyPollError

    client = _make_client()
    result = client._map_spotipy_exception(_rate_limited_exc(42))
    assert isinstance(result, SpotifyPollError)
    assert result.retry_after == "42"  # type: ignore[attr-defined]


def test_map_spotipy_exception_429_no_headers_retry_after_is_none():
    """_map_spotipy_exception(429 with no Retry-After header) sets retry_after=None."""
    from integrations.spotify.client import SpotifyPollError

    client = _make_client()
    exc = _spotify_exc(429)
    exc.headers = {}
    result = client._map_spotipy_exception(exc)
    assert isinstance(result, SpotifyPollError)
    assert result.retry_after is None  # type: ignore[attr-defined]


def test_map_spotipy_exception_500_returns_poll_error():
    """_map_spotipy_exception(500) returns SpotifyPollError."""
    from integrations.spotify.client import SpotifyPollError

    client = _make_client()
    result = client._map_spotipy_exception(_spotify_exc(500))
    assert isinstance(result, SpotifyPollError)


def test_map_spotipy_exception_non_spotify_exc_returns_poll_error():
    """_map_spotipy_exception(non-spotipy exception) returns SpotifyPollError."""
    from integrations.spotify.client import SpotifyPollError

    client = _make_client()
    result = client._map_spotipy_exception(RuntimeError("network failure"))
    assert isinstance(result, SpotifyPollError)


# ---------------------------------------------------------------------------
# _extract_tracks_from_items
# ---------------------------------------------------------------------------


def test_extract_tracks_from_items_handles_wrapped_and_raw():
    """_extract_tracks_from_items() handles both {track: {...}} and raw track dicts."""
    from integrations.spotify.client import _extract_tracks_from_items

    items = [
        # wrapped (playlist_tracks / saved_tracks)
        {
            "track": {
                "id": "t1",
                "name": "Song A",
                "artists": [{"name": "Artist A"}],
                "album": {"name": "Album A"},
                "duration_ms": 180000,
                "uri": "spotify:track:t1",
            }
        },
        # raw (hypothetical)
        {
            "id": "t2",
            "name": "Song B",
            "artists": [{"name": "Artist B"}],
            "album": {"name": "Album B"},
            "duration_ms": 200000,
            "uri": "spotify:track:t2",
        },
        # None entry should be skipped
        None,
        # wrapped with track=None should be skipped
        {"track": None},
    ]

    result = _extract_tracks_from_items(items)
    assert len(result) == 2
    assert result[0].name == "Song A"
    assert result[1].name == "Song B"
