"""Tests for the WIKI_LOOKUP intent in brain/intent_parser.py.

Covers:
- German trigger phrases ("was weißt du über X", variants)
- English trigger phrases ("what do you know about X", variants)
- Topic extraction (trigger stripped, only topic remains)
- Non-matching queries do NOT classify as WIKI_LOOKUP
- Confidence ≥ 0.80 on clear matches
- Mixed-case and punctuation tolerance
"""

from __future__ import annotations

import pytest

from brain.intent_parser import Intent, IntentParser


@pytest.fixture
def parser() -> IntentParser:
    """Return a fresh IntentParser instance."""
    return IntentParser()


# ---------------------------------------------------------------------------
# German trigger phrases
# ---------------------------------------------------------------------------


class TestWikiLookupGermanTriggers:
    """German trigger phrases route to WIKI_LOOKUP with high confidence."""

    @pytest.mark.asyncio
    async def test_was_weisst_du_ueber_trigger(self, parser: IntentParser):
        """'was weißt du über X' → WIKI_LOOKUP."""
        result = await parser.classify_intent("was weißt du über meine Schwester", language="de")
        assert result.intent == Intent.WIKI_LOOKUP

    @pytest.mark.asyncio
    async def test_was_weist_du_ueber_no_umlaut_trigger(self, parser: IntentParser):
        """'was weisst du über X' (no umlaut) → WIKI_LOOKUP via fallback pattern."""
        result = await parser.classify_intent("was weiß du über meinen Bruder", language="de")
        assert result.intent == Intent.WIKI_LOOKUP

    @pytest.mark.asyncio
    async def test_was_hast_du_ueber_trigger(self, parser: IntentParser):
        """'was hast du über X' → WIKI_LOOKUP."""
        result = await parser.classify_intent("was hast du über das Meeting", language="de")
        assert result.intent == Intent.WIKI_LOOKUP

    @pytest.mark.asyncio
    async def test_kennst_du_etwas_ueber_trigger(self, parser: IntentParser):
        """'kennst du etwas über X' → WIKI_LOOKUP."""
        result = await parser.classify_intent("kennst du etwas über meine Schwester", language="de")
        assert result.intent == Intent.WIKI_LOOKUP

    @pytest.mark.asyncio
    async def test_kennst_du_ueber_without_etwas(self, parser: IntentParser):
        """'kennst du über X' (without etwas) → WIKI_LOOKUP."""
        result = await parser.classify_intent("kennst du über das Projekt", language="de")
        assert result.intent == Intent.WIKI_LOOKUP

    @pytest.mark.asyncio
    async def test_german_trigger_confidence_at_least_0_80(self, parser: IntentParser):
        """German WIKI_LOOKUP matches must have confidence ≥ 0.80."""
        result = await parser.classify_intent("was weißt du über meine Schwester", language="de")
        assert result.confidence >= 0.80


# ---------------------------------------------------------------------------
# English trigger phrases
# ---------------------------------------------------------------------------


class TestWikiLookupEnglishTriggers:
    """English trigger phrases route to WIKI_LOOKUP with high confidence."""

    @pytest.mark.asyncio
    async def test_what_do_you_know_about_trigger(self, parser: IntentParser):
        """'what do you know about X' → WIKI_LOOKUP."""
        result = await parser.classify_intent(
            "what do you know about my sister", language="en"
        )
        assert result.intent == Intent.WIKI_LOOKUP

    @pytest.mark.asyncio
    async def test_do_you_know_anything_about_trigger(self, parser: IntentParser):
        """'do you know anything about X' → WIKI_LOOKUP."""
        result = await parser.classify_intent(
            "do you know anything about the project", language="en"
        )
        assert result.intent == Intent.WIKI_LOOKUP

    @pytest.mark.asyncio
    async def test_do_you_know_something_about_trigger(self, parser: IntentParser):
        """'do you know something about X' → WIKI_LOOKUP."""
        result = await parser.classify_intent(
            "do you know something about my brother", language="en"
        )
        assert result.intent == Intent.WIKI_LOOKUP

    @pytest.mark.asyncio
    async def test_what_have_you_learned_about_trigger(self, parser: IntentParser):
        """'what have you learned about X' → WIKI_LOOKUP."""
        result = await parser.classify_intent(
            "what have you learned about the deployment", language="en"
        )
        assert result.intent == Intent.WIKI_LOOKUP

    @pytest.mark.asyncio
    async def test_tell_me_what_you_know_about_trigger(self, parser: IntentParser):
        """'tell me what you know about X' → WIKI_LOOKUP."""
        result = await parser.classify_intent(
            "tell me what you know about Alice", language="en"
        )
        assert result.intent == Intent.WIKI_LOOKUP

    @pytest.mark.asyncio
    async def test_english_trigger_confidence_at_least_0_80(self, parser: IntentParser):
        """English WIKI_LOOKUP matches must have confidence ≥ 0.80."""
        result = await parser.classify_intent(
            "what do you know about my sister", language="en"
        )
        assert result.confidence >= 0.80


# ---------------------------------------------------------------------------
# Topic extraction
# ---------------------------------------------------------------------------


class TestWikiLookupTopicExtraction:
    """_extract_wiki_params strips trigger prefix, leaving only the topic."""

    @pytest.mark.asyncio
    async def test_german_topic_extracted_correctly(self, parser: IntentParser):
        """'was weißt du über meine Schwester' → topic='meine schwester'."""
        result = await parser.classify_intent("was weißt du über meine Schwester", language="de")
        assert result.intent == Intent.WIKI_LOOKUP
        topic = result.params.get("topic", "")
        assert "schwester" in topic.lower()

    @pytest.mark.asyncio
    async def test_english_topic_extracted_correctly(self, parser: IntentParser):
        """'what do you know about my sister' → topic='my sister'."""
        result = await parser.classify_intent(
            "what do you know about my sister", language="en"
        )
        assert result.intent == Intent.WIKI_LOOKUP
        topic = result.params.get("topic", "")
        assert "sister" in topic.lower()

    @pytest.mark.asyncio
    async def test_topic_has_no_trigger_phrase_residue_german(self, parser: IntentParser):
        """German: 'was weißt du über' is NOT part of the extracted topic."""
        result = await parser.classify_intent("was weißt du über das Wetter", language="de")
        topic = result.params.get("topic", "")
        assert "was weißt du" not in topic.lower()
        assert "weißt" not in topic.lower()

    @pytest.mark.asyncio
    async def test_topic_has_no_trigger_phrase_residue_english(self, parser: IntentParser):
        """English: 'what do you know about' is NOT part of the extracted topic."""
        result = await parser.classify_intent(
            "what do you know about the weather", language="en"
        )
        topic = result.params.get("topic", "")
        assert "what do you know" not in topic.lower()

    @pytest.mark.asyncio
    async def test_topic_stripped_of_trailing_punctuation(self, parser: IntentParser):
        """Trailing '?' is stripped from the extracted topic."""
        result = await parser.classify_intent(
            "what do you know about my sister?", language="en"
        )
        topic = result.params.get("topic", "")
        assert not topic.endswith("?")

    @pytest.mark.asyncio
    async def test_topic_params_key_present_on_match(self, parser: IntentParser):
        """IntentResult.params always has a 'topic' key on WIKI_LOOKUP match."""
        result = await parser.classify_intent(
            "was weißt du über meine Schwester", language="de"
        )
        assert result.intent == Intent.WIKI_LOOKUP
        assert "topic" in result.params


# ---------------------------------------------------------------------------
# Non-matching queries
# ---------------------------------------------------------------------------


class TestWikiLookupNonMatches:
    """Queries that should NOT classify as WIKI_LOOKUP."""

    @pytest.mark.asyncio
    async def test_calendar_query_not_wiki_lookup(self, parser: IntentParser):
        """A calendar query does not become WIKI_LOOKUP."""
        result = await parser.classify_intent("wie spät ist es?", language="de")
        assert result.intent != Intent.WIKI_LOOKUP

    @pytest.mark.asyncio
    async def test_weather_query_not_wiki_lookup(self, parser: IntentParser):
        """A weather question does not become WIKI_LOOKUP."""
        result = await parser.classify_intent(
            "what's the weather like today?", language="en"
        )
        assert result.intent != Intent.WIKI_LOOKUP

    @pytest.mark.asyncio
    async def test_spotify_request_not_wiki_lookup(self, parser: IntentParser):
        """A Spotify play request does not become WIKI_LOOKUP."""
        result = await parser.classify_intent("play some music", language="en")
        assert result.intent != Intent.WIKI_LOOKUP

    @pytest.mark.asyncio
    async def test_empty_text_not_wiki_lookup(self, parser: IntentParser):
        """Empty input defaults to CHAT, not WIKI_LOOKUP."""
        result = await parser.classify_intent("", language="en")
        assert result.intent == Intent.CHAT

    @pytest.mark.asyncio
    async def test_generic_question_not_wiki_lookup_german(self, parser: IntentParser):
        """A generic German question does not trigger WIKI_LOOKUP."""
        result = await parser.classify_intent("was ist das?", language="de")
        assert result.intent != Intent.WIKI_LOOKUP

    @pytest.mark.asyncio
    async def test_partial_trigger_not_wiki_lookup(self, parser: IntentParser):
        """A partial trigger phrase without topic does not match WIKI_LOOKUP."""
        # "know about" alone, without full phrase, should not match
        result = await parser.classify_intent("do you know this?", language="en")
        assert result.intent != Intent.WIKI_LOOKUP


# ---------------------------------------------------------------------------
# Mixed-case and punctuation tolerance
# ---------------------------------------------------------------------------


class TestWikiLookupCaseAndPunctuation:
    """WIKI_LOOKUP matching tolerates case differences and punctuation."""

    @pytest.mark.asyncio
    async def test_uppercase_trigger_still_matches(self, parser: IntentParser):
        """Uppercase variant still classifies as WIKI_LOOKUP (re.IGNORECASE)."""
        result = await parser.classify_intent(
            "WHAT DO YOU KNOW ABOUT my sister", language="en"
        )
        assert result.intent == Intent.WIKI_LOOKUP

    @pytest.mark.asyncio
    async def test_mixed_case_trigger_still_matches(self, parser: IntentParser):
        """Mixed-case variant still classifies as WIKI_LOOKUP."""
        result = await parser.classify_intent(
            "What Do You Know About my sister", language="en"
        )
        assert result.intent == Intent.WIKI_LOOKUP

    @pytest.mark.asyncio
    async def test_trailing_question_mark_does_not_prevent_match(self, parser: IntentParser):
        """Trailing '?' does not prevent matching."""
        result = await parser.classify_intent(
            "was weißt du über meine Schwester?", language="de"
        )
        assert result.intent == Intent.WIKI_LOOKUP

    @pytest.mark.asyncio
    async def test_topic_contains_actual_subject(self, parser: IntentParser):
        """Extracted topic from 'what do you know about my sister' contains 'sister'."""
        result = await parser.classify_intent(
            "what do you know about my sister", language="en"
        )
        topic = result.params.get("topic", "")
        assert len(topic) > 0
        assert "my sister" in topic or "sister" in topic
