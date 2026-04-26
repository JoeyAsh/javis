"""Unit tests for SpotifyAgent.

Mocks SpotifyClient — no live API calls.
Covers three intents in DE + EN, plus all error edge cases.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_client() -> MagicMock:
    """Return a MagicMock shaped like SpotifyClient."""
    mock = MagicMock()
    mock.list_playlists = AsyncMock()
    mock.search = AsyncMock()
    mock.play_context = AsyncMock()
    mock.play_uris = AsyncMock()
    mock.add_to_queue = AsyncMock()
    return mock


def _make_playlist(name: str, uri: str) -> Any:
    from integrations.spotify.client import SpotifyPlaylist

    return SpotifyPlaylist(id="pl1", name=name, owner="user", track_count=10, uri=uri)


def _make_track(name: str, artist: str, uri: str) -> Any:
    from integrations.spotify.client import SpotifyTrackResult

    return SpotifyTrackResult(id="t1", name=name, artist=artist, album="Album", duration_ms=200000, uri=uri)


def _make_search_results(tracks: list) -> Any:
    from integrations.spotify.client import SpotifySearchResults

    return SpotifySearchResults(tracks=tracks, artists=[], albums=[], playlists=[])


@pytest.fixture()
def agent() -> Any:
    from brain.agents.spotify_agent import SpotifyAgent

    client = _make_client()
    return SpotifyAgent(client), client


# ---------------------------------------------------------------------------
# SPOTIFY_PLAY_CONTEXT — EN
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_play_context_en_fuzzy_match_exact_substring():
    """SPOTIFY_PLAY_CONTEXT EN: substring match on playlist name calls play_context."""
    from brain.agents.spotify_agent import SpotifyAgent

    client = _make_client()
    client.list_playlists = AsyncMock(
        return_value=[_make_playlist("Coding Sessions", "spotify:playlist:pl1")]
    )

    agent = SpotifyAgent(client)
    result = await agent.run("SPOTIFY_PLAY_CONTEXT", {"query": "coding"}, "en")

    assert result.success is True
    assert "Coding Sessions" in result.spoken_response
    client.play_context.assert_called_once_with("spotify:playlist:pl1")


@pytest.mark.asyncio
async def test_play_context_de_fuzzy_match():
    """SPOTIFY_PLAY_CONTEXT DE: fuzzy match on 'Deep Focus' → German spoken response."""
    from brain.agents.spotify_agent import SpotifyAgent

    client = _make_client()
    client.list_playlists = AsyncMock(
        return_value=[_make_playlist("Deep Focus", "spotify:playlist:pl2")]
    )

    agent = SpotifyAgent(client)
    result = await agent.run("SPOTIFY_PLAY_CONTEXT", {"query": "Deep Focus"}, "de")

    assert result.success is True
    assert "Deep Focus" in result.spoken_response
    # German template
    assert "Spiele" in result.spoken_response or "spiele" in result.spoken_response.lower()


@pytest.mark.asyncio
async def test_play_context_no_playlist_match_en():
    """SPOTIFY_PLAY_CONTEXT EN: no fuzzy match → spoken not-found fallback."""
    from brain.agents.spotify_agent import SpotifyAgent

    client = _make_client()
    client.list_playlists = AsyncMock(
        return_value=[_make_playlist("Metal Hits", "spotify:playlist:pl3")]
    )

    agent = SpotifyAgent(client)
    result = await agent.run("SPOTIFY_PLAY_CONTEXT", {"query": "jazz classics"}, "en")

    assert result.success is False
    assert "couldn't find" in result.spoken_response.lower() or "no playlist" in result.spoken_response.lower()
    client.play_context.assert_not_called()


@pytest.mark.asyncio
async def test_play_context_no_playlist_match_de():
    """SPOTIFY_PLAY_CONTEXT DE: no match → German spoken not-found fallback."""
    from brain.agents.spotify_agent import SpotifyAgent

    client = _make_client()
    client.list_playlists = AsyncMock(
        return_value=[_make_playlist("Metal Hits", "spotify:playlist:pl3")]
    )

    agent = SpotifyAgent(client)
    result = await agent.run("SPOTIFY_PLAY_CONTEXT", {"query": "jazz klassik"}, "de")

    assert result.success is False
    assert "keine playlist" in result.spoken_response.lower() or "tut mir leid" in result.spoken_response.lower()


@pytest.mark.asyncio
async def test_play_context_empty_playlist_list_returns_fallback():
    """SPOTIFY_PLAY_CONTEXT: empty playlist list → not-found fallback."""
    from brain.agents.spotify_agent import SpotifyAgent

    client = _make_client()
    client.list_playlists = AsyncMock(return_value=[])

    agent = SpotifyAgent(client)
    result = await agent.run("SPOTIFY_PLAY_CONTEXT", {"query": "any playlist"}, "en")

    assert result.success is False
    client.play_context.assert_not_called()


# ---------------------------------------------------------------------------
# SPOTIFY_SEARCH — EN
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_play_en_plays_top_track():
    """SPOTIFY_SEARCH EN: top search result is played via play_uris."""
    from brain.agents.spotify_agent import SpotifyAgent

    client = _make_client()
    client.search = AsyncMock(
        return_value=_make_search_results(
            [_make_track("Midnight City", "M83", "spotify:track:t1")]
        )
    )

    agent = SpotifyAgent(client)
    result = await agent.run("SPOTIFY_SEARCH", {"query": "Midnight City"}, "en")

    assert result.success is True
    assert "Midnight City" in result.spoken_response
    assert "M83" in result.spoken_response
    client.play_uris.assert_called_once_with(["spotify:track:t1"])


@pytest.mark.asyncio
async def test_search_play_de_uses_german_template():
    """SPOTIFY_SEARCH DE: spoken response uses German template."""
    from brain.agents.spotify_agent import SpotifyAgent

    client = _make_client()
    client.search = AsyncMock(
        return_value=_make_search_results(
            [_make_track("Oblivion", "Grimes", "spotify:track:t2")]
        )
    )

    agent = SpotifyAgent(client)
    result = await agent.run("SPOTIFY_SEARCH", {"query": "Oblivion"}, "de")

    assert result.success is True
    assert "Oblivion" in result.spoken_response
    assert "Grimes" in result.spoken_response
    assert "Spiele" in result.spoken_response


@pytest.mark.asyncio
async def test_search_play_empty_results_en():
    """SPOTIFY_SEARCH EN: empty search results → no-result spoken fallback."""
    from brain.agents.spotify_agent import SpotifyAgent

    client = _make_client()
    client.search = AsyncMock(return_value=_make_search_results([]))

    agent = SpotifyAgent(client)
    result = await agent.run("SPOTIFY_SEARCH", {"query": "xyznotexist"}, "en")

    assert result.success is False
    assert "no results" in result.spoken_response.lower() or "not found" in result.spoken_response.lower() or "no results found" in result.spoken_response.lower()
    client.play_uris.assert_not_called()


@pytest.mark.asyncio
async def test_search_play_empty_results_de():
    """SPOTIFY_SEARCH DE: empty search → German no-result fallback."""
    from brain.agents.spotify_agent import SpotifyAgent

    client = _make_client()
    client.search = AsyncMock(return_value=_make_search_results([]))

    agent = SpotifyAgent(client)
    result = await agent.run("SPOTIFY_SEARCH", {"query": "xyznotexist"}, "de")

    assert result.success is False
    assert "keine ergebnisse" in result.spoken_response.lower() or "keine" in result.spoken_response.lower()


@pytest.mark.asyncio
async def test_search_builds_query_with_artist_param():
    """SPOTIFY_SEARCH: 'query' + 'artist' params are combined for the search call."""
    from brain.agents.spotify_agent import SpotifyAgent

    client = _make_client()
    client.search = AsyncMock(return_value=_make_search_results([]))

    agent = SpotifyAgent(client)
    await agent.run("SPOTIFY_SEARCH", {"query": "Come Together", "artist": "Beatles"}, "en")

    call_args = client.search.call_args
    q = call_args[0][0]
    assert "Come Together" in q
    assert "Beatles" in q


# ---------------------------------------------------------------------------
# SPOTIFY_QUEUE — EN + DE
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_queue_add_en_adds_top_track():
    """SPOTIFY_QUEUE EN: top search result is added via add_to_queue."""
    from brain.agents.spotify_agent import SpotifyAgent

    client = _make_client()
    client.search = AsyncMock(
        return_value=_make_search_results(
            [_make_track("Begin Again", "Purity Ring", "spotify:track:t3")]
        )
    )

    agent = SpotifyAgent(client)
    result = await agent.run("SPOTIFY_QUEUE", {"query": "Begin Again"}, "en")

    assert result.success is True
    assert "Begin Again" in result.spoken_response
    assert "Purity Ring" in result.spoken_response
    client.add_to_queue.assert_called_once_with("spotify:track:t3")
    client.play_uris.assert_not_called()


@pytest.mark.asyncio
async def test_queue_add_de_uses_german_template():
    """SPOTIFY_QUEUE DE: spoken response uses German queue template."""
    from brain.agents.spotify_agent import SpotifyAgent

    client = _make_client()
    client.search = AsyncMock(
        return_value=_make_search_results(
            [_make_track("Intro", "The xx", "spotify:track:t4")]
        )
    )

    agent = SpotifyAgent(client)
    result = await agent.run("SPOTIFY_QUEUE", {"query": "Intro The xx"}, "de")

    assert result.success is True
    assert "Warteschlange" in result.spoken_response or "hinzugefügt" in result.spoken_response.lower()


@pytest.mark.asyncio
async def test_queue_add_empty_results_en():
    """SPOTIFY_QUEUE EN: empty search → no-result spoken fallback."""
    from brain.agents.spotify_agent import SpotifyAgent

    client = _make_client()
    client.search = AsyncMock(return_value=_make_search_results([]))

    agent = SpotifyAgent(client)
    result = await agent.run("SPOTIFY_QUEUE", {"query": "xyznotexist"}, "en")

    assert result.success is False
    client.add_to_queue.assert_not_called()


@pytest.mark.asyncio
async def test_queue_add_empty_results_de():
    """SPOTIFY_QUEUE DE: empty search → German not-found fallback."""
    from brain.agents.spotify_agent import SpotifyAgent

    client = _make_client()
    client.search = AsyncMock(return_value=_make_search_results([]))

    agent = SpotifyAgent(client)
    result = await agent.run("SPOTIFY_QUEUE", {"query": "xyznotexist"}, "de")

    assert result.success is False
    assert "konnte" in result.spoken_response.lower()


# ---------------------------------------------------------------------------
# Error paths — SpotifyAuthError, SpotifyPremiumError, SpotifyPollError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auth_error_returns_spoken_fallback_en():
    """SpotifyAuthError during any intent → spoken auth-required response (EN)."""
    from brain.agents.spotify_agent import SpotifyAgent
    from integrations.spotify.client import SpotifyAuthError

    client = _make_client()
    client.list_playlists = AsyncMock(side_effect=SpotifyAuthError("expired"))

    agent = SpotifyAgent(client)
    result = await agent.run("SPOTIFY_PLAY_CONTEXT", {"query": "coding"}, "en")

    assert result.success is False
    assert "authentication" in result.spoken_response.lower() or "reconnect" in result.spoken_response.lower()


@pytest.mark.asyncio
async def test_auth_error_returns_spoken_fallback_de():
    """SpotifyAuthError → German auth-required spoken response."""
    from brain.agents.spotify_agent import SpotifyAgent
    from integrations.spotify.client import SpotifyAuthError

    client = _make_client()
    client.list_playlists = AsyncMock(side_effect=SpotifyAuthError("expired"))

    agent = SpotifyAgent(client)
    result = await agent.run("SPOTIFY_PLAY_CONTEXT", {"query": "coding"}, "de")

    assert result.success is False
    assert "authentifizierung" in result.spoken_response.lower() or "hud" in result.spoken_response.lower()


@pytest.mark.asyncio
async def test_premium_error_returns_premium_fallback_en():
    """SpotifyPremiumError → spoken 'Premium required' response (EN)."""
    from brain.agents.spotify_agent import SpotifyAgent
    from integrations.spotify.client import SpotifyPremiumError

    client = _make_client()
    client.search = AsyncMock(side_effect=SpotifyPremiumError("premium"))

    agent = SpotifyAgent(client)
    result = await agent.run("SPOTIFY_SEARCH", {"query": "test"}, "en")

    assert result.success is False
    assert "premium" in result.spoken_response.lower()


@pytest.mark.asyncio
async def test_premium_error_returns_premium_fallback_de():
    """SpotifyPremiumError → German Premium-required spoken response."""
    from brain.agents.spotify_agent import SpotifyAgent
    from integrations.spotify.client import SpotifyPremiumError

    client = _make_client()
    client.search = AsyncMock(side_effect=SpotifyPremiumError("premium"))

    agent = SpotifyAgent(client)
    result = await agent.run("SPOTIFY_SEARCH", {"query": "test"}, "de")

    assert result.success is False
    assert "premium" in result.spoken_response.lower()


@pytest.mark.asyncio
async def test_rate_limit_error_returns_rate_limited_fallback():
    """SpotifyPollError → spoken rate-limited response."""
    from brain.agents.spotify_agent import SpotifyAgent
    from integrations.spotify.client import SpotifyPollError

    client = _make_client()
    client.search = AsyncMock(side_effect=SpotifyPollError("rate limited"))

    agent = SpotifyAgent(client)
    result = await agent.run("SPOTIFY_SEARCH", {"query": "test"}, "en")

    assert result.success is False
    assert "rate" in result.spoken_response.lower() or "try again" in result.spoken_response.lower()


@pytest.mark.asyncio
async def test_unknown_task_returns_failure():
    """Unknown task string → failure result with polite no-op spoken response."""
    from brain.agents.spotify_agent import SpotifyAgent

    client = _make_client()
    agent = SpotifyAgent(client)
    result = await agent.run("SPOTIFY_UNKNOWN_TASK", {}, "en")

    assert result.success is False
    assert "don't know" in result.spoken_response.lower()


# ---------------------------------------------------------------------------
# No active device edge case (play_context raises generic exception)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_play_context_no_active_device_returns_generic_error():
    """play_context() raising a generic Exception → generic spoken error response."""
    from brain.agents.spotify_agent import SpotifyAgent

    client = _make_client()
    client.list_playlists = AsyncMock(
        return_value=[_make_playlist("Coding Sessions", "spotify:playlist:pl1")]
    )
    client.play_context = AsyncMock(side_effect=Exception("No active device"))

    agent = SpotifyAgent(client)
    result = await agent.run("SPOTIFY_PLAY_CONTEXT", {"query": "coding"}, "en")

    assert result.success is False
    assert "issue" in result.spoken_response.lower() or "problem" in result.spoken_response.lower()
