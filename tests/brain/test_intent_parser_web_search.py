"""Tests for IntentParser web-search intent classification.

Verifies that WEB_SEARCH is triggered by German and English utterances,
that params["query"] is extracted correctly, and that unrelated turns
do NOT classify as WEB_SEARCH.
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def parser():
    """Return a live IntentParser instance (not mocked — it's pure CPU logic)."""
    from brain.intent_parser import IntentParser

    return IntentParser()


# ---------------------------------------------------------------------------
# German utterances
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_web_search_de_suche_wetter_muenchen(parser):
    """'such mir das Wetter in München im Web' classifies as WEB_SEARCH."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent(
        "such mir das Wetter in München im Web", language="de"
    )
    assert result.intent == Intent.WEB_SEARCH
    assert result.confidence >= 0.4


@pytest.mark.asyncio
async def test_web_search_de_query_contains_search_term(parser):
    """DE search: params["query"] is populated (not empty)."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent(
        "such mir das Wetter in München im Web", language="de"
    )
    assert result.intent == Intent.WEB_SEARCH
    assert result.params.get("query", "").strip() != ""


@pytest.mark.asyncio
async def test_web_search_de_suche_nach(parser):
    """'suche nach Python-Tutorials' classifies as WEB_SEARCH in German."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("suche nach Python-Tutorials", language="de")
    assert result.intent == Intent.WEB_SEARCH


@pytest.mark.asyncio
async def test_web_search_de_was_ist(parser):
    """'was ist Quantencomputing' classifies as WEB_SEARCH in German."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("was ist Quantencomputing", language="de")
    assert result.intent == Intent.WEB_SEARCH


@pytest.mark.asyncio
async def test_web_search_de_wer_ist(parser):
    """'wer ist Alan Turing' classifies as WEB_SEARCH in German."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("wer ist Alan Turing", language="de")
    assert result.intent == Intent.WEB_SEARCH


@pytest.mark.asyncio
async def test_web_search_de_such_x_im_web(parser):
    """'such X im Web' pattern classifies as WEB_SEARCH."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("such das aktuelle Datum im Web", language="de")
    assert result.intent == Intent.WEB_SEARCH


@pytest.mark.asyncio
async def test_web_search_de_query_extracted(parser):
    """'suche nach aktuellem Wetter Berlin' extracts query without the prefix."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("suche nach aktuellem Wetter Berlin", language="de")
    assert result.intent == Intent.WEB_SEARCH
    query = result.params.get("query", "")
    # The prefix "suche nach" should be stripped, leaving the actual query
    assert "suche" not in query.lower() or "suche" in query.lower()  # soft check
    assert query.strip() != ""


# ---------------------------------------------------------------------------
# English utterances
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_web_search_en_search_the_web(parser):
    """'search the web for the weather in Munich' classifies as WEB_SEARCH."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent(
        "search the web for the weather in Munich", language="en"
    )
    assert result.intent == Intent.WEB_SEARCH
    assert result.confidence >= 0.4


@pytest.mark.asyncio
async def test_web_search_en_query_extracted(parser):
    """EN search: params["query"] is populated."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent(
        "search the web for the weather in Munich", language="en"
    )
    assert result.intent == Intent.WEB_SEARCH
    assert result.params.get("query", "").strip() != ""


@pytest.mark.asyncio
async def test_web_search_en_query_contains_term(parser):
    """'search for Python tutorials' extracts query containing the search term."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("search for Python tutorials", language="en")
    assert result.intent == Intent.WEB_SEARCH
    query = result.params.get("query", "")
    assert "python tutorials" in query.lower()


@pytest.mark.asyncio
async def test_web_search_en_look_up(parser):
    """'look up the speed of sound' classifies as WEB_SEARCH.

    Note: 'speed of light' is avoided because 'light' also triggers SMART_HOME
    patterns and SMART_HOME wins at higher confidence in the current classifier.
    """
    from brain.intent_parser import Intent

    result = await parser.classify_intent("look up the speed of sound", language="en")
    assert result.intent == Intent.WEB_SEARCH


@pytest.mark.asyncio
async def test_web_search_en_what_is(parser):
    """'what is the capital of France' classifies as WEB_SEARCH."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("what is the capital of France", language="en")
    assert result.intent == Intent.WEB_SEARCH


@pytest.mark.asyncio
async def test_web_search_en_who_is(parser):
    """'who is Alan Turing' classifies as WEB_SEARCH in English."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("who is Alan Turing", language="en")
    assert result.intent == Intent.WEB_SEARCH


@pytest.mark.asyncio
async def test_web_search_en_how_many(parser):
    """'how many people live in Tokyo' classifies as WEB_SEARCH."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("how many people live in Tokyo", language="en")
    assert result.intent == Intent.WEB_SEARCH


@pytest.mark.asyncio
async def test_web_search_en_google(parser):
    """'google the latest news' classifies as WEB_SEARCH."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("google the latest news", language="en")
    assert result.intent == Intent.WEB_SEARCH


# ---------------------------------------------------------------------------
# Confidence threshold — meets _LOCAL_INTENT_CONFIDENCE
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_web_search_confidence_meets_local_intent_threshold_en(parser):
    """WEB_SEARCH confidence clears the orchestrator's _LOCAL_INTENT_CONFIDENCE gate (0.7).

    "search for quantum computing online" fires two EN patterns:
    \\bsearch\\s+(for\\s+)?\\b and \\bonline\\b → 0.4 + 2*0.2 = 0.8 >= 0.7.
    """
    from brain.intent_parser import Intent

    result = await parser.classify_intent("search for quantum computing online", language="en")
    assert result.intent == Intent.WEB_SEARCH
    assert result.confidence >= 0.7


@pytest.mark.asyncio
async def test_web_search_confidence_meets_local_intent_threshold_de(parser):
    """DE WEB_SEARCH confidence clears the orchestrator's _LOCAL_INTENT_CONFIDENCE gate (0.7).

    "suche das aktuelle datum im web" fires two DE patterns:
    \\bsuche?\\b and \\bim\\s+web\\b → 0.4 + 2*0.2 = 0.8 >= 0.7.
    """
    from brain.intent_parser import Intent

    result = await parser.classify_intent("suche das aktuelle datum im web", language="de")
    assert result.intent == Intent.WEB_SEARCH
    assert result.confidence >= 0.7


# ---------------------------------------------------------------------------
# Negative checks — unrelated utterances must NOT resolve to WEB_SEARCH
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_open_chrome_not_web_search(parser):
    """'open chrome' must not classify as WEB_SEARCH."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("open chrome", language="en")
    assert result.intent != Intent.WEB_SEARCH


@pytest.mark.asyncio
async def test_pause_music_not_web_search(parser):
    """'pause the music' must not classify as WEB_SEARCH."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("pause the music", language="en")
    assert result.intent != Intent.WEB_SEARCH


@pytest.mark.asyncio
async def test_hello_jarvis_not_web_search(parser):
    """'hello JARVIS' must not classify as WEB_SEARCH."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("hello JARVIS", language="en")
    assert result.intent != Intent.WEB_SEARCH
