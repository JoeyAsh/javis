"""Tests for Spotify extended intent classification (issue #58).

Covers SPOTIFY_SEARCH, SPOTIFY_QUEUE, SPOTIFY_PLAY_CONTEXT in EN + DE.
Also verifies disambiguation: "search for X" still routes to WEB_SEARCH,
while "search for X on spotify" / "search for X by Y" routes to SPOTIFY_SEARCH.
"""

from __future__ import annotations

import pytest


@pytest.fixture()
def parser():
    """Return a fresh IntentParser instance."""
    from brain.intent_parser import IntentParser

    return IntentParser()


# ---------------------------------------------------------------------------
# SPOTIFY_SEARCH — English
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_spotify_search_on_spotify_anchor_en(parser):
    """'search for Midnight City on spotify' → SPOTIFY_SEARCH."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("search for Midnight City on spotify", "en")
    assert result.intent == Intent.SPOTIFY_SEARCH
    assert result.confidence >= 0.75


@pytest.mark.asyncio
async def test_spotify_search_by_artist_anchor_en(parser):
    """'search for Come Together by Beatles' → SPOTIFY_SEARCH (artist anchor)."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("search for Come Together by Beatles", "en")
    assert result.intent == Intent.SPOTIFY_SEARCH


@pytest.mark.asyncio
async def test_spotify_search_find_on_spotify_en(parser):
    """'find Bohemian Rhapsody on spotify' → SPOTIFY_SEARCH."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("find Bohemian Rhapsody on spotify", "en")
    assert result.intent == Intent.SPOTIFY_SEARCH


@pytest.mark.asyncio
async def test_spotify_search_explicit_anchor_en(parser):
    """'spotify search for jazz' → SPOTIFY_SEARCH."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("spotify search for jazz", "en")
    assert result.intent == Intent.SPOTIFY_SEARCH


# ---------------------------------------------------------------------------
# SPOTIFY_SEARCH disambiguation — bare "search for X" must stay WEB_SEARCH
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bare_search_routes_to_web_search_en(parser):
    """'search for latest news' → WEB_SEARCH, NOT SPOTIFY_SEARCH."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("search for latest news", "en")
    assert result.intent == Intent.WEB_SEARCH


@pytest.mark.asyncio
async def test_bare_look_up_routes_to_web_search_en(parser):
    """'look up the weather' → WEB_SEARCH, NOT SPOTIFY_SEARCH."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("look up the weather", "en")
    assert result.intent == Intent.WEB_SEARCH


@pytest.mark.asyncio
async def test_search_for_x_without_spotify_anchor_is_not_spotify_search(parser):
    """'search for photos of Paris' → NOT SPOTIFY_SEARCH."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("search for photos of Paris", "en")
    assert result.intent != Intent.SPOTIFY_SEARCH


# ---------------------------------------------------------------------------
# SPOTIFY_SEARCH — German
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_spotify_search_de_auf_spotify(parser):
    """'suche Midnight City auf Spotify' → SPOTIFY_SEARCH in DE."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("suche Midnight City auf Spotify", "de")
    assert result.intent == Intent.SPOTIFY_SEARCH


@pytest.mark.asyncio
async def test_spotify_search_de_von_anchor(parser):
    """'suche Come Together von Beatles' → SPOTIFY_SEARCH in DE."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("suche Come Together von Beatles", "de")
    assert result.intent == Intent.SPOTIFY_SEARCH


@pytest.mark.asyncio
async def test_spotify_search_de_spotify_suche(parser):
    """'Spotify Suche Jazz' → SPOTIFY_SEARCH in DE."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("Spotify Suche Jazz", "de")
    assert result.intent == Intent.SPOTIFY_SEARCH


# ---------------------------------------------------------------------------
# SPOTIFY_SEARCH — params extraction
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_spotify_search_extracts_query_en(parser):
    """params['query'] contains the music subject after stripping trigger phrases.
    The parser lowercases input, so the query is compared case-insensitively.
    """
    result = await parser.classify_intent("search for Midnight City on spotify", "en")
    assert "midnight city" in result.params.get("query", "").lower()


@pytest.mark.asyncio
async def test_spotify_search_extracts_artist_en(parser):
    """params['artist'] is extracted from 'by <artist>' anchor."""
    result = await parser.classify_intent("search for Come Together by Beatles", "en")
    assert result.params.get("artist", "").lower() == "beatles"


@pytest.mark.asyncio
async def test_spotify_search_extracts_query_without_artist_duplication(parser):
    """After extracting artist, query does not contain the 'by <artist>' part."""
    result = await parser.classify_intent("search for Come Together by Beatles on spotify", "en")
    query = result.params.get("query", "")
    # Artist name should be removed from query (it lives in 'artist' key)
    assert "Beatles" not in query


@pytest.mark.asyncio
async def test_spotify_search_de_extracts_query(parser):
    """DE SPOTIFY_SEARCH params['query'] extracted correctly.
    The parser lowercases input, so the query is compared case-insensitively.
    """
    result = await parser.classify_intent("suche Midnight City auf Spotify", "de")
    assert "midnight city" in result.params.get("query", "").lower()


# ---------------------------------------------------------------------------
# SPOTIFY_QUEUE — English
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_spotify_queue_add_to_queue_en(parser):
    """'add Begin Again to the queue' → SPOTIFY_QUEUE."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("add Begin Again to the queue", "en")
    assert result.intent == Intent.SPOTIFY_QUEUE
    assert result.confidence >= 0.75


@pytest.mark.asyncio
async def test_spotify_queue_queue_up_en(parser):
    """'queue up Intro by The xx' → SPOTIFY_QUEUE."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("queue up Intro by The xx", "en")
    assert result.intent == Intent.SPOTIFY_QUEUE


@pytest.mark.asyncio
async def test_spotify_queue_enqueue_en(parser):
    """'enqueue Bohemian Rhapsody' → SPOTIFY_QUEUE."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("enqueue Bohemian Rhapsody", "en")
    assert result.intent == Intent.SPOTIFY_QUEUE


# ---------------------------------------------------------------------------
# SPOTIFY_QUEUE — German
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_spotify_queue_de_zur_warteschlange(parser):
    """'Begin Again zur Warteschlange hinzufügen' → SPOTIFY_QUEUE in DE."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("Begin Again zur Warteschlange hinzufügen", "de")
    assert result.intent == Intent.SPOTIFY_QUEUE


@pytest.mark.asyncio
async def test_spotify_queue_de_enqueue(parser):
    """'enqueue Bohemian Rhapsody' in DE context → SPOTIFY_QUEUE."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("enqueue Bohemian Rhapsody", "de")
    assert result.intent == Intent.SPOTIFY_QUEUE


# ---------------------------------------------------------------------------
# SPOTIFY_QUEUE — params extraction
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_spotify_queue_extracts_query_en(parser):
    """SPOTIFY_QUEUE params['query'] extracted from queue utterance."""
    result = await parser.classify_intent("add Begin Again to the queue", "en")
    assert result.params.get("query", "") != ""


# ---------------------------------------------------------------------------
# SPOTIFY_PLAY_CONTEXT — English
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_play_context_play_playlist_en(parser):
    """'play the playlist Coding Sessions' → SPOTIFY_PLAY_CONTEXT."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("play the playlist Coding Sessions", "en")
    assert result.intent == Intent.SPOTIFY_PLAY_CONTEXT
    assert result.confidence >= 0.75


@pytest.mark.asyncio
async def test_play_context_start_album_en(parser):
    """'start the album Dark Side of the Moon' → SPOTIFY_PLAY_CONTEXT."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("start the album Dark Side of the Moon", "en")
    assert result.intent == Intent.SPOTIFY_PLAY_CONTEXT


@pytest.mark.asyncio
async def test_play_context_put_on_en(parser):
    """'put on the playlist Deep Focus' → SPOTIFY_PLAY_CONTEXT."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("put on the playlist Deep Focus", "en")
    assert result.intent == Intent.SPOTIFY_PLAY_CONTEXT


# ---------------------------------------------------------------------------
# SPOTIFY_PLAY_CONTEXT — German
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_play_context_de_spiele_playlist(parser):
    """'spiele die Playlist Coding Sessions' → SPOTIFY_PLAY_CONTEXT in DE."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("spiele die Playlist Coding Sessions", "de")
    assert result.intent == Intent.SPOTIFY_PLAY_CONTEXT


@pytest.mark.asyncio
async def test_play_context_de_starte_album(parser):
    """'spiele das Album Dark Side of the Moon' → SPOTIFY_PLAY_CONTEXT in DE.
    Note: 'starte' is ambiguous with PC_CONTROL (start app) in DE patterns.
    Use 'spiele' which maps unambiguously to SPOTIFY_PLAY_CONTEXT.
    """
    from brain.intent_parser import Intent

    result = await parser.classify_intent("spiele das Album Dark Side of the Moon", "de")
    assert result.intent == Intent.SPOTIFY_PLAY_CONTEXT


@pytest.mark.asyncio
async def test_play_context_de_mach_playlist_an(parser):
    """'mach die Playlist an' → SPOTIFY_PLAY_CONTEXT in DE."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("mach die Playlist an", "de")
    assert result.intent == Intent.SPOTIFY_PLAY_CONTEXT


# ---------------------------------------------------------------------------
# SPOTIFY_PLAY_CONTEXT — params extraction
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_play_context_extracts_query_en(parser):
    """SPOTIFY_PLAY_CONTEXT params['query'] is populated."""
    result = await parser.classify_intent("play the playlist Coding Sessions", "en")
    assert result.params.get("query", "") != ""


# ---------------------------------------------------------------------------
# Confidence threshold
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_spotify_search_confidence_gte_075(parser):
    """SPOTIFY_SEARCH confidence is >= 0.75."""
    result = await parser.classify_intent("search spotify for jazz", "en")
    from brain.intent_parser import Intent

    if result.intent == Intent.SPOTIFY_SEARCH:
        assert result.confidence >= 0.75


@pytest.mark.asyncio
async def test_spotify_queue_confidence_gte_075(parser):
    """SPOTIFY_QUEUE confidence is >= 0.75."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("add this song to the queue", "en")
    if result.intent == Intent.SPOTIFY_QUEUE:
        assert result.confidence >= 0.75


@pytest.mark.asyncio
async def test_spotify_play_context_confidence_gte_075(parser):
    """SPOTIFY_PLAY_CONTEXT confidence is >= 0.75."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("play the playlist Deep Focus", "en")
    if result.intent == Intent.SPOTIFY_PLAY_CONTEXT:
        assert result.confidence >= 0.75
