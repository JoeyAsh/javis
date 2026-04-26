"""Unit tests for Spotify REST API route handlers.

Uses aiohttp.test_utils.TestServer + TestClient directly (no pytest-aiohttp).
The module-level _spotify_client is replaced per test via unittest.mock.patch.object.

No live HTTP calls, no real spotipy, no real Spotify.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer, TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_client(authenticated: bool = True) -> MagicMock:
    """Return a MagicMock shaped like a SpotifyClient."""
    mock = MagicMock()
    mock.is_authenticated.return_value = authenticated
    return mock


async def _build_app() -> web.Application:
    """Build a minimal aiohttp app containing only the Spotify route handlers."""
    from api.ws_server import (
        spotify_playlists_handler,
        spotify_playlist_tracks_handler,
        spotify_album_tracks_handler,
        spotify_saved_tracks_handler,
        spotify_saved_albums_handler,
        spotify_search_handler,
        spotify_queue_get_handler,
        spotify_queue_post_handler,
        spotify_play_context_handler,
        spotify_play_uris_handler,
        spotify_token_handler,
    )

    app = web.Application()
    app.router.add_get("/api/spotify/playlists", spotify_playlists_handler)
    app.router.add_get("/api/spotify/playlists/{id}/tracks", spotify_playlist_tracks_handler)
    app.router.add_get("/api/spotify/albums/{id}/tracks", spotify_album_tracks_handler)
    app.router.add_get("/api/spotify/me/tracks", spotify_saved_tracks_handler)
    app.router.add_get("/api/spotify/me/albums", spotify_saved_albums_handler)
    app.router.add_get("/api/spotify/search", spotify_search_handler)
    app.router.add_get("/api/spotify/queue", spotify_queue_get_handler)
    app.router.add_post("/api/spotify/queue", spotify_queue_post_handler)
    app.router.add_post("/api/spotify/play/context", spotify_play_context_handler)
    app.router.add_post("/api/spotify/play/uris", spotify_play_uris_handler)
    app.router.add_get("/api/spotify/token", spotify_token_handler)
    return app


# Shared loop fixture
@pytest.fixture
def loop(event_loop):
    return event_loop


# ---------------------------------------------------------------------------
# Context-manager helper to spin up a test client per test
# ---------------------------------------------------------------------------

from contextlib import asynccontextmanager


@asynccontextmanager
async def _client_ctx(mock_client: MagicMock):
    """Build app + start TestServer + yield TestClient, then shut down."""
    import api.ws_server as ws_mod

    app = await _build_app()
    server = TestServer(app)
    client = TestClient(server)

    with patch.object(ws_mod, "_spotify_client", mock_client):
        await client.start_server()
        try:
            yield client
        finally:
            await client.close()


# ---------------------------------------------------------------------------
# GET /api/spotify/playlists
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_playlists_401_when_unauthenticated():
    """GET /api/spotify/playlists returns 401 when client not authenticated."""
    mock = _make_mock_client(authenticated=False)
    async with _client_ctx(mock) as client:
        resp = await client.get("/api/spotify/playlists")
        assert resp.status == 401
        body = await resp.json()
        assert body["error"] == "unauthenticated"


@pytest.mark.asyncio
async def test_get_playlists_happy_path():
    """GET /api/spotify/playlists returns 200 with items array."""
    from integrations.spotify.client import SpotifyPlaylist

    mock = _make_mock_client()
    mock.list_playlists = AsyncMock(
        return_value=[
            SpotifyPlaylist(
                id="pl1", name="Test Playlist", owner="user", track_count=10, uri="spotify:playlist:pl1"
            )
        ]
    )

    async with _client_ctx(mock) as client:
        resp = await client.get("/api/spotify/playlists")
        assert resp.status == 200
        body = await resp.json()
        assert body["items"][0]["id"] == "pl1"
        assert body["items"][0]["name"] == "Test Playlist"


@pytest.mark.asyncio
async def test_get_playlists_401_on_auth_error():
    """GET /api/spotify/playlists returns 401 when SpotifyAuthError is raised."""
    from integrations.spotify.client import SpotifyAuthError

    mock = _make_mock_client()
    mock.list_playlists = AsyncMock(side_effect=SpotifyAuthError("expired"))

    async with _client_ctx(mock) as client:
        resp = await client.get("/api/spotify/playlists")
        assert resp.status == 401


@pytest.mark.asyncio
async def test_get_playlists_402_on_premium_error():
    """GET /api/spotify/playlists returns 402 when SpotifyPremiumError is raised."""
    from integrations.spotify.client import SpotifyPremiumError

    mock = _make_mock_client()
    mock.list_playlists = AsyncMock(side_effect=SpotifyPremiumError("premium"))

    async with _client_ctx(mock) as client:
        resp = await client.get("/api/spotify/playlists")
        assert resp.status == 402


@pytest.mark.asyncio
async def test_get_playlists_429_with_retry_after():
    """GET /api/spotify/playlists returns 429 with Retry-After header."""
    from integrations.spotify.client import SpotifyPollError

    exc = SpotifyPollError("rate limited")
    exc.retry_after = 30  # type: ignore[attr-defined]

    mock = _make_mock_client()
    mock.list_playlists = AsyncMock(side_effect=exc)

    async with _client_ctx(mock) as client:
        resp = await client.get("/api/spotify/playlists")
        assert resp.status == 429
        assert resp.headers.get("Retry-After") == "30"


@pytest.mark.asyncio
async def test_get_playlists_500_on_generic_error():
    """GET /api/spotify/playlists returns 500 on unexpected exception."""
    mock = _make_mock_client()
    mock.list_playlists = AsyncMock(side_effect=RuntimeError("db crash"))

    async with _client_ctx(mock) as client:
        resp = await client.get("/api/spotify/playlists")
        assert resp.status == 500


# ---------------------------------------------------------------------------
# GET /api/spotify/playlists/{id}/tracks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_playlist_tracks_happy_path():
    """GET /api/spotify/playlists/{id}/tracks returns 200 with track items."""
    from integrations.spotify.client import SpotifyTrackResult

    mock = _make_mock_client()
    mock.playlist_tracks = AsyncMock(
        return_value=[
            SpotifyTrackResult(
                id="t1", name="Song", artist="Artist", album="Album", duration_ms=200000, uri="spotify:track:t1"
            )
        ]
    )

    async with _client_ctx(mock) as client:
        resp = await client.get("/api/spotify/playlists/pl1/tracks")
        assert resp.status == 200
        body = await resp.json()
        assert body["items"][0]["name"] == "Song"


@pytest.mark.asyncio
async def test_get_playlist_tracks_401_unauthenticated():
    """GET /api/spotify/playlists/{id}/tracks returns 401 when unauthenticated."""
    mock = _make_mock_client(authenticated=False)

    async with _client_ctx(mock) as client:
        resp = await client.get("/api/spotify/playlists/pl1/tracks")
        assert resp.status == 401


# ---------------------------------------------------------------------------
# GET /api/spotify/albums/{id}/tracks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_album_tracks_happy_path():
    """GET /api/spotify/albums/{id}/tracks returns 200 with track items."""
    from integrations.spotify.client import SpotifyTrackResult

    mock = _make_mock_client()
    mock.album_tracks = AsyncMock(
        return_value=[
            SpotifyTrackResult(
                id="t1", name="Intro", artist="The xx", album="", duration_ms=130000, uri="spotify:track:t1"
            )
        ]
    )

    async with _client_ctx(mock) as client:
        resp = await client.get("/api/spotify/albums/al1/tracks")
        assert resp.status == 200


@pytest.mark.asyncio
async def test_get_album_tracks_401_unauthenticated():
    """GET /api/spotify/albums/{id}/tracks returns 401 when unauthenticated."""
    mock = _make_mock_client(authenticated=False)

    async with _client_ctx(mock) as client:
        resp = await client.get("/api/spotify/albums/al1/tracks")
        assert resp.status == 401


# ---------------------------------------------------------------------------
# GET /api/spotify/me/tracks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_saved_tracks_happy_path():
    """GET /api/spotify/me/tracks returns 200 with saved track items."""
    from integrations.spotify.client import SpotifyTrackResult

    mock = _make_mock_client()
    mock.saved_tracks = AsyncMock(
        return_value=[
            SpotifyTrackResult(
                id="t1", name="Oblivion", artist="Grimes", album="Visions", duration_ms=253000, uri="spotify:track:t1"
            )
        ]
    )

    async with _client_ctx(mock) as client:
        resp = await client.get("/api/spotify/me/tracks")
        assert resp.status == 200
        body = await resp.json()
        assert body["items"][0]["name"] == "Oblivion"


@pytest.mark.asyncio
async def test_get_saved_tracks_401_unauthenticated():
    """GET /api/spotify/me/tracks returns 401 when unauthenticated."""
    mock = _make_mock_client(authenticated=False)

    async with _client_ctx(mock) as client:
        resp = await client.get("/api/spotify/me/tracks")
        assert resp.status == 401


# ---------------------------------------------------------------------------
# GET /api/spotify/me/albums
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_saved_albums_happy_path():
    """GET /api/spotify/me/albums returns 200 with album list."""
    mock = _make_mock_client()
    mock.saved_albums = AsyncMock(
        return_value=[
            {
                "id": "al1", "name": "Visions", "artist": "Grimes",
                "total_tracks": 14, "uri": "spotify:album:al1", "release_date": "2012",
            }
        ]
    )

    async with _client_ctx(mock) as client:
        resp = await client.get("/api/spotify/me/albums")
        assert resp.status == 200
        body = await resp.json()
        assert body["items"][0]["name"] == "Visions"


@pytest.mark.asyncio
async def test_get_saved_albums_401_unauthenticated():
    """GET /api/spotify/me/albums returns 401 when unauthenticated."""
    mock = _make_mock_client(authenticated=False)

    async with _client_ctx(mock) as client:
        resp = await client.get("/api/spotify/me/albums")
        assert resp.status == 401


# ---------------------------------------------------------------------------
# GET /api/spotify/search
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_happy_path():
    """GET /api/spotify/search?q=test returns 200 with result buckets."""
    from integrations.spotify.client import SpotifySearchResults, SpotifyTrackResult

    mock = _make_mock_client()
    mock.search = AsyncMock(
        return_value=SpotifySearchResults(
            tracks=[SpotifyTrackResult(id="t1", name="Song", artist="A", album="B", duration_ms=200000, uri="spotify:track:t1")],
            artists=[],
            albums=[],
            playlists=[],
        )
    )

    async with _client_ctx(mock) as client:
        resp = await client.get("/api/spotify/search?q=test")
        assert resp.status == 200
        body = await resp.json()
        assert len(body["tracks"]) == 1


@pytest.mark.asyncio
async def test_search_400_missing_q_param():
    """GET /api/spotify/search without q= returns 400."""
    mock = _make_mock_client()

    async with _client_ctx(mock) as client:
        resp = await client.get("/api/spotify/search")
        assert resp.status == 400
        body = await resp.json()
        assert "q" in body["error"]


@pytest.mark.asyncio
async def test_search_401_unauthenticated():
    """GET /api/spotify/search returns 401 when unauthenticated."""
    mock = _make_mock_client(authenticated=False)

    async with _client_ctx(mock) as client:
        resp = await client.get("/api/spotify/search?q=test")
        assert resp.status == 401


@pytest.mark.asyncio
async def test_search_429_with_retry_after():
    """GET /api/spotify/search returns 429 + Retry-After on rate limit."""
    from integrations.spotify.client import SpotifyPollError

    exc = SpotifyPollError("rate limited")
    exc.retry_after = 15  # type: ignore[attr-defined]

    mock = _make_mock_client()
    mock.search = AsyncMock(side_effect=exc)

    async with _client_ctx(mock) as client:
        resp = await client.get("/api/spotify/search?q=test")
        assert resp.status == 429
        assert resp.headers.get("Retry-After") == "15"


# ---------------------------------------------------------------------------
# GET /api/spotify/queue
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_queue_happy_path():
    """GET /api/spotify/queue returns 200 with queue items."""
    from integrations.spotify.client import SpotifyQueueItem

    mock = _make_mock_client()
    mock.get_queue = AsyncMock(
        return_value=[
            SpotifyQueueItem(position=0, name="Song", artist="Artist", uri="spotify:track:t1")
        ]
    )

    async with _client_ctx(mock) as client:
        resp = await client.get("/api/spotify/queue")
        assert resp.status == 200
        body = await resp.json()
        assert body["items"][0]["name"] == "Song"


@pytest.mark.asyncio
async def test_get_queue_401_unauthenticated():
    """GET /api/spotify/queue returns 401 when unauthenticated."""
    mock = _make_mock_client(authenticated=False)

    async with _client_ctx(mock) as client:
        resp = await client.get("/api/spotify/queue")
        assert resp.status == 401


@pytest.mark.asyncio
async def test_get_queue_402_premium_error():
    """GET /api/spotify/queue returns 402 on SpotifyPremiumError."""
    from integrations.spotify.client import SpotifyPremiumError

    mock = _make_mock_client()
    mock.get_queue = AsyncMock(side_effect=SpotifyPremiumError("premium"))

    async with _client_ctx(mock) as client:
        resp = await client.get("/api/spotify/queue")
        assert resp.status == 402


# ---------------------------------------------------------------------------
# POST /api/spotify/queue
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_queue_happy_path():
    """POST /api/spotify/queue with valid uri returns 200 empty body."""
    mock = _make_mock_client()
    mock.add_to_queue = AsyncMock()

    async with _client_ctx(mock) as client:
        resp = await client.post(
            "/api/spotify/queue",
            data=json.dumps({"uri": "spotify:track:t1"}),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 200
        mock.add_to_queue.assert_called_once_with("spotify:track:t1")


@pytest.mark.asyncio
async def test_post_queue_400_missing_uri():
    """POST /api/spotify/queue without uri field returns 400."""
    mock = _make_mock_client()

    async with _client_ctx(mock) as client:
        resp = await client.post(
            "/api/spotify/queue",
            data=json.dumps({}),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 400


@pytest.mark.asyncio
async def test_post_queue_401_unauthenticated():
    """POST /api/spotify/queue returns 401 when unauthenticated."""
    mock = _make_mock_client(authenticated=False)

    async with _client_ctx(mock) as client:
        resp = await client.post(
            "/api/spotify/queue",
            data=json.dumps({"uri": "spotify:track:t1"}),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 401


@pytest.mark.asyncio
async def test_post_queue_400_invalid_json():
    """POST /api/spotify/queue with malformed JSON returns 400."""
    mock = _make_mock_client()

    async with _client_ctx(mock) as client:
        resp = await client.post(
            "/api/spotify/queue",
            data="not-json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 400


# ---------------------------------------------------------------------------
# POST /api/spotify/play/context
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_play_context_happy_path():
    """POST /api/spotify/play/context with context_uri returns 200."""
    mock = _make_mock_client()
    mock.play_context = AsyncMock()

    async with _client_ctx(mock) as client:
        resp = await client.post(
            "/api/spotify/play/context",
            data=json.dumps({"context_uri": "spotify:playlist:pl1"}),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 200
        mock.play_context.assert_called_once_with(
            "spotify:playlist:pl1", offset_uri=None, device_id=None
        )


@pytest.mark.asyncio
async def test_post_play_context_400_missing_context_uri():
    """POST /api/spotify/play/context without context_uri returns 400."""
    mock = _make_mock_client()

    async with _client_ctx(mock) as client:
        resp = await client.post(
            "/api/spotify/play/context",
            data=json.dumps({}),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 400


@pytest.mark.asyncio
async def test_post_play_context_401_unauthenticated():
    """POST /api/spotify/play/context returns 401 when unauthenticated."""
    mock = _make_mock_client(authenticated=False)

    async with _client_ctx(mock) as client:
        resp = await client.post(
            "/api/spotify/play/context",
            data=json.dumps({"context_uri": "spotify:playlist:pl1"}),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 401


@pytest.mark.asyncio
async def test_post_play_context_402_premium_error():
    """POST /api/spotify/play/context returns 402 on SpotifyPremiumError."""
    from integrations.spotify.client import SpotifyPremiumError

    mock = _make_mock_client()
    mock.play_context = AsyncMock(side_effect=SpotifyPremiumError("premium"))

    async with _client_ctx(mock) as client:
        resp = await client.post(
            "/api/spotify/play/context",
            data=json.dumps({"context_uri": "spotify:playlist:pl1"}),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 402


# ---------------------------------------------------------------------------
# POST /api/spotify/play/uris
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_play_uris_happy_path():
    """POST /api/spotify/play/uris with uris list returns 200."""
    mock = _make_mock_client()
    mock.play_uris = AsyncMock()

    async with _client_ctx(mock) as client:
        resp = await client.post(
            "/api/spotify/play/uris",
            data=json.dumps({"uris": ["spotify:track:t1"]}),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 200
        mock.play_uris.assert_called_once_with(["spotify:track:t1"], device_id=None)


@pytest.mark.asyncio
async def test_post_play_uris_400_missing_uris():
    """POST /api/spotify/play/uris without uris returns 400."""
    mock = _make_mock_client()

    async with _client_ctx(mock) as client:
        resp = await client.post(
            "/api/spotify/play/uris",
            data=json.dumps({}),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 400


@pytest.mark.asyncio
async def test_post_play_uris_400_empty_uris_list():
    """POST /api/spotify/play/uris with empty uris list returns 400."""
    mock = _make_mock_client()

    async with _client_ctx(mock) as client:
        resp = await client.post(
            "/api/spotify/play/uris",
            data=json.dumps({"uris": []}),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 400


@pytest.mark.asyncio
async def test_post_play_uris_401_unauthenticated():
    """POST /api/spotify/play/uris returns 401 when unauthenticated."""
    mock = _make_mock_client(authenticated=False)

    async with _client_ctx(mock) as client:
        resp = await client.post(
            "/api/spotify/play/uris",
            data=json.dumps({"uris": ["spotify:track:t1"]}),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 401


@pytest.mark.asyncio
async def test_post_play_uris_402_premium_error():
    """POST /api/spotify/play/uris returns 402 on SpotifyPremiumError."""
    from integrations.spotify.client import SpotifyPremiumError

    mock = _make_mock_client()
    mock.play_uris = AsyncMock(side_effect=SpotifyPremiumError("premium"))

    async with _client_ctx(mock) as client:
        resp = await client.post(
            "/api/spotify/play/uris",
            data=json.dumps({"uris": ["spotify:track:t1"]}),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 402


@pytest.mark.asyncio
async def test_post_play_uris_500_on_generic_exception():
    """POST /api/spotify/play/uris returns 500 on unexpected error."""
    mock = _make_mock_client()
    mock.play_uris = AsyncMock(side_effect=RuntimeError("unexpected"))

    async with _client_ctx(mock) as client:
        resp = await client.post(
            "/api/spotify/play/uris",
            data=json.dumps({"uris": ["spotify:track:t1"]}),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 500


# ---------------------------------------------------------------------------
# GET /api/spotify/token  (issue #84)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_token_happy_path():
    """GET /api/spotify/token returns 200 with access_token and expires_in."""
    mock = _make_mock_client()
    mock.get_access_token = AsyncMock(return_value=("tok-abc-123", 3600))

    async with _client_ctx(mock) as client:
        resp = await client.get("/api/spotify/token")
        assert resp.status == 200
        body = await resp.json()
        assert body["access_token"] == "tok-abc-123"
        assert body["expires_in"] == 3600


@pytest.mark.asyncio
async def test_get_token_401_when_unauthenticated():
    """GET /api/spotify/token returns 401 when client is not authenticated."""
    mock = _make_mock_client(authenticated=False)

    async with _client_ctx(mock) as client:
        resp = await client.get("/api/spotify/token")
        assert resp.status == 401
        body = await resp.json()
        assert body["error"] == "unauthenticated"


@pytest.mark.asyncio
async def test_get_token_401_on_spotify_auth_error():
    """GET /api/spotify/token returns 401 when get_access_token raises SpotifyAuthError."""
    from integrations.spotify.client import SpotifyAuthError

    mock = _make_mock_client()
    mock.get_access_token = AsyncMock(side_effect=SpotifyAuthError("no token"))

    async with _client_ctx(mock) as client:
        resp = await client.get("/api/spotify/token")
        assert resp.status == 401
        body = await resp.json()
        assert body["error"] == "unauthenticated"


@pytest.mark.asyncio
async def test_get_token_500_on_generic_error():
    """GET /api/spotify/token returns 500 on unexpected exception."""
    mock = _make_mock_client()
    mock.get_access_token = AsyncMock(side_effect=RuntimeError("internal failure"))

    async with _client_ctx(mock) as client:
        resp = await client.get("/api/spotify/token")
        assert resp.status == 500
        body = await resp.json()
        assert "internal failure" in body["error"]


# ---------------------------------------------------------------------------
# POST /api/spotify/play/context — device_id targeting  (issue #84)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_play_context_with_device_id_passes_through():
    """POST /api/spotify/play/context with device_id calls play_context with device_id."""
    mock = _make_mock_client()
    mock.play_context = AsyncMock()

    async with _client_ctx(mock) as client:
        resp = await client.post(
            "/api/spotify/play/context",
            data=json.dumps(
                {"context_uri": "spotify:playlist:pl1", "device_id": "dev-abc123"}
            ),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 200
        mock.play_context.assert_called_once_with(
            "spotify:playlist:pl1", offset_uri=None, device_id="dev-abc123"
        )


@pytest.mark.asyncio
async def test_post_play_context_without_device_id_passes_none():
    """POST /api/spotify/play/context without device_id calls play_context(device_id=None)."""
    mock = _make_mock_client()
    mock.play_context = AsyncMock()

    async with _client_ctx(mock) as client:
        resp = await client.post(
            "/api/spotify/play/context",
            data=json.dumps({"context_uri": "spotify:playlist:pl1"}),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 200
        mock.play_context.assert_called_once_with(
            "spotify:playlist:pl1", offset_uri=None, device_id=None
        )


# ---------------------------------------------------------------------------
# POST /api/spotify/play/uris — device_id targeting  (issue #84)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_play_uris_with_device_id_passes_through():
    """POST /api/spotify/play/uris with device_id calls play_uris with device_id."""
    mock = _make_mock_client()
    mock.play_uris = AsyncMock()

    async with _client_ctx(mock) as client:
        resp = await client.post(
            "/api/spotify/play/uris",
            data=json.dumps(
                {"uris": ["spotify:track:t1"], "device_id": "dev-abc123"}
            ),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 200
        mock.play_uris.assert_called_once_with(
            ["spotify:track:t1"], device_id="dev-abc123"
        )


@pytest.mark.asyncio
async def test_post_play_uris_without_device_id_passes_none():
    """POST /api/spotify/play/uris without device_id calls play_uris(device_id=None)."""
    mock = _make_mock_client()
    mock.play_uris = AsyncMock()

    async with _client_ctx(mock) as client:
        resp = await client.post(
            "/api/spotify/play/uris",
            data=json.dumps({"uris": ["spotify:track:t1"]}),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 200
        mock.play_uris.assert_called_once_with(
            ["spotify:track:t1"], device_id=None
        )
