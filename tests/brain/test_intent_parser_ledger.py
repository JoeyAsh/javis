"""Tests for Intent.LEDGER_QUERY classification — AC #12.

Verifies that the canonical German and English ledger-query phrases
classify as Intent.LEDGER_QUERY with confidence >= 0.7.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def parser():
    """Return a live IntentParser instance."""
    from brain.intent_parser import IntentParser

    return IntentParser()


# ---------------------------------------------------------------------------
# AC #12 — DE phrases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ledger_query_de_canonical(parser):
    """'was hast du heute aufgezeichnet' → LEDGER_QUERY, conf >= 0.7 (DE)."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent(
        "was hast du heute aufgezeichnet", language="de"
    )
    assert result.intent == Intent.LEDGER_QUERY
    assert result.confidence >= 0.7


@pytest.mark.asyncio
async def test_ledger_query_de_question_mark(parser):
    """'Was hast du heute aufgezeichnet?' → LEDGER_QUERY (DE, with punctuation)."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent(
        "Was hast du heute aufgezeichnet?", language="de"
    )
    assert result.intent == Intent.LEDGER_QUERY
    assert result.confidence >= 0.7


@pytest.mark.asyncio
async def test_ledger_query_de_geloggt(parser):
    """'was wurde heute geloggt' → LEDGER_QUERY (DE)."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent(
        "was wurde heute geloggt", language="de"
    )
    assert result.intent == Intent.LEDGER_QUERY
    assert result.confidence >= 0.7


@pytest.mark.asyncio
async def test_ledger_query_de_zeig_ledger(parser):
    """'zeig mir das ledger' → LEDGER_QUERY (DE)."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent(
        "zeig mir das ledger", language="de"
    )
    assert result.intent == Intent.LEDGER_QUERY
    assert result.confidence >= 0.7


# ---------------------------------------------------------------------------
# AC #12 — EN phrases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ledger_query_en_canonical(parser):
    """'what have you logged today' → LEDGER_QUERY, conf >= 0.7 (EN)."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent(
        "what have you logged today", language="en"
    )
    assert result.intent == Intent.LEDGER_QUERY
    assert result.confidence >= 0.7


@pytest.mark.asyncio
async def test_ledger_query_en_show_ledger(parser):
    """'show me the ledger today' → LEDGER_QUERY (EN)."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent(
        "show me the ledger today", language="en"
    )
    assert result.intent == Intent.LEDGER_QUERY
    assert result.confidence >= 0.7


@pytest.mark.asyncio
async def test_ledger_query_en_events_today(parser):
    """'what events today' → LEDGER_QUERY (EN)."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent(
        "what events today", language="en"
    )
    assert result.intent == Intent.LEDGER_QUERY
    assert result.confidence >= 0.7


# ---------------------------------------------------------------------------
# Negative — unrelated phrases should NOT classify as LEDGER_QUERY.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ledger_query_not_matched_for_chat(parser):
    """A generic chat phrase does not classify as LEDGER_QUERY."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent(
        "what is the weather today", language="en"
    )
    assert result.intent != Intent.LEDGER_QUERY


@pytest.mark.asyncio
async def test_ledger_query_not_matched_for_spotify(parser):
    """A Spotify phrase does not classify as LEDGER_QUERY."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent(
        "play music on spotify", language="en"
    )
    assert result.intent != Intent.LEDGER_QUERY
