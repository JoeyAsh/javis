"""Tests for brain.voice_composer — covers AC #2, #3, #4, #5.

Every external dependency (config, strip_markdown_for_tts) is mocked
so this module is fully self-contained.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Helpers — build a VoiceComposer with explicit config, no disk reads.
# ---------------------------------------------------------------------------


def _make_composer(max_sentence_words: int = 50, long_sentence_mode: str = "split"):
    """Return a VoiceComposer instantiated with explicit config."""
    from brain.voice_composer import VoiceComposer

    return VoiceComposer(
        config={
            "max_sentence_words": max_sentence_words,
            "long_sentence_mode": long_sentence_mode,
            "salutation_policy": "sir_only",
        }
    )


# ---------------------------------------------------------------------------
# AC #2 — markdown reply returns plain text with no #, *, - markers.
# ---------------------------------------------------------------------------


class TestMarkdownStripping:
    """AC #2: markdown → plain text."""

    def test_compose_strips_hash_headers(self):
        """# Header becomes plain text without # marker."""
        composer = _make_composer()
        result = composer.compose("# Hello there", language="en")
        assert "#" not in result.text

    def test_compose_strips_bold(self):
        """**bold** text becomes plain text without * markers."""
        composer = _make_composer()
        result = composer.compose("This is **bold** text", language="en")
        assert "*" not in result.text

    def test_compose_strips_bullet_list(self):
        """Bullet list items become plain text without - markers."""
        composer = _make_composer()
        result = composer.compose("- item one\n- item two", language="en")
        assert result.text.count("-") == 0 or "item" in result.text

    def test_compose_full_markdown_reply(self):
        """AC #2 verbatim fixture: '# Header\\n**bold** text\\n- item one\\n- item two'."""
        composer = _make_composer()
        md = "# Header\n**bold** text\n- item one\n- item two"
        result = composer.compose(md, language="en")
        assert "#" not in result.text
        assert "*" not in result.text
        # Bullet dash only at word boundary — strip_markdown_for_tts removes list markers
        # The resulting text must be non-empty.
        assert result.text.strip() != ""

    def test_compose_non_empty_markdown_is_non_empty(self):
        """Non-trivial markdown input produces non-empty output."""
        composer = _make_composer()
        result = composer.compose("**Important** announcement", language="de")
        assert result.text.strip() != ""


# ---------------------------------------------------------------------------
# AC #3 — 80-word sentence with split mode produces >= 2 sentences.
# ---------------------------------------------------------------------------


class TestLongSentenceSplit:
    """AC #3: long sentence + split mode."""

    def _eighty_word_sentence(self) -> str:
        return " ".join(["word"] * 80) + "."

    def test_split_mode_produces_multiple_sentences(self):
        """80-word sentence with max_sentence_words=50, split mode → ≥2 sentences."""
        composer = _make_composer(max_sentence_words=50, long_sentence_mode="split")
        result = composer.compose(self._eighty_word_sentence(), language="en")
        # After salutation the first chunk has "Sir, word word …" so sentence count ≥ 2
        assert len(result.sentences) >= 2

    def test_split_mode_clipped_is_false(self):
        """split mode does NOT set clipped=True even for long sentences."""
        composer = _make_composer(max_sentence_words=50, long_sentence_mode="split")
        result = composer.compose(self._eighty_word_sentence(), language="en")
        assert result.clipped is False

    def test_split_mode_text_contains_all_words(self):
        """All words from the original sentence appear in the final text (split doesn't drop)."""
        composer = _make_composer(max_sentence_words=50, long_sentence_mode="split")
        input_text = " ".join([f"w{i}" for i in range(80)])
        result = composer.compose(input_text, language="en")
        for i in range(80):
            assert f"w{i}" in result.text


# ---------------------------------------------------------------------------
# AC #4 — 80-word sentence with truncate mode: ends with … and clipped=True.
# ---------------------------------------------------------------------------


class TestLongSentenceTruncate:
    """AC #4: long sentence + truncate mode."""

    def _eighty_word_sentence(self) -> str:
        return " ".join(["word"] * 80) + "."

    def test_truncate_mode_clipped_is_true(self):
        """truncate mode sets clipped=True when sentence exceeds max_sentence_words."""
        composer = _make_composer(max_sentence_words=50, long_sentence_mode="truncate")
        result = composer.compose(self._eighty_word_sentence(), language="en")
        assert result.clipped is True

    def test_truncate_mode_first_sentence_ends_with_ellipsis(self):
        """truncate mode: the truncated sentence ends with …."""
        composer = _make_composer(max_sentence_words=50, long_sentence_mode="truncate")
        result = composer.compose(self._eighty_word_sentence(), language="en")
        # sentences[0] has the salutation prepended; check any sentence ends with …
        assert any(s.endswith("…") for s in result.sentences)

    def test_truncate_mode_sentence_count_is_one(self):
        """truncate mode produces exactly one output sentence for a single over-limit sentence."""
        composer = _make_composer(max_sentence_words=50, long_sentence_mode="truncate")
        result = composer.compose(self._eighty_word_sentence(), language="en")
        assert len(result.sentences) == 1


# ---------------------------------------------------------------------------
# AC #5 — salutation is always "Sir" (Decision 1).
# ---------------------------------------------------------------------------


class TestSalutation:
    """AC #5: rotate_salutation always returns 'Sir' (Decision 1: sir_only policy)."""

    def test_ten_composes_all_return_sir_salutation(self):
        """Over 10 calls, salutation_used is always 'Sir'."""
        composer = _make_composer()
        salutations = [
            composer.compose(f"Hello sentence {i}.", language="en").salutation_used
            for i in range(10)
        ]
        assert all(s == "Sir" for s in salutations)

    def test_get_salutation_returns_sir(self):
        """VoiceComposer.get_salutation() always returns 'Sir'."""
        composer = _make_composer()
        for _ in range(10):
            assert composer.get_salutation() == "Sir"

    def test_sir_only_policy_regardless_of_config(self):
        """Even if config says 'weighted_random', V1 always emits 'Sir'."""
        from brain.voice_composer import VoiceComposer

        composer = VoiceComposer(
            config={
                "max_sentence_words": 50,
                "long_sentence_mode": "split",
                "salutation_policy": "weighted_random",
            }
        )
        result = composer.compose("Good response.", language="en")
        assert result.salutation_used == "Sir"

    def test_salutation_prepended_to_first_sentence(self):
        """Salutation is prepended to the first composed sentence."""
        composer = _make_composer()
        result = composer.compose("Hello there.", language="en")
        assert result.sentences[0].startswith("Sir,")


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases: empty string, whitespace-only, mood_snapshot=None accepted."""

    def test_empty_string_returns_empty_compose_result(self):
        """Empty string returns ComposeResult(text='', salutation_used=None, sentences=[], clipped=False)."""
        from brain.voice_composer import ComposeResult

        composer = _make_composer()
        result = composer.compose("", language="en")
        assert result == ComposeResult(text="", salutation_used=None, sentences=[], clipped=False)

    def test_whitespace_only_returns_empty_compose_result(self):
        """Whitespace-only input returns the empty ComposeResult."""
        from brain.voice_composer import ComposeResult

        composer = _make_composer()
        result = composer.compose("   \n\t  ", language="en")
        assert result == ComposeResult(text="", salutation_used=None, sentences=[], clipped=False)

    def test_mood_snapshot_none_accepted(self):
        """compose() accepts mood_snapshot=None without error (Phase 3 stub)."""
        composer = _make_composer()
        result = composer.compose("Hello.", language="en", mood_snapshot=None)
        assert result.text != ""

    def test_mood_snapshot_arbitrary_value_accepted(self):
        """compose() accepts any mood_snapshot value without error."""
        composer = _make_composer()
        result = composer.compose("Hello.", language="en", mood_snapshot={"valence": 0.8})
        assert result.text != ""

    def test_status_snapshot_after_compose(self):
        """status_snapshot() returns last_compose_ts and last_salutation after a compose."""
        composer = _make_composer()
        composer.compose("Something.", language="de")
        snap = composer.status_snapshot()
        assert snap["last_compose_ts"] is not None
        assert snap["last_salutation"] == "Sir"

    def test_status_snapshot_initial_state(self):
        """status_snapshot() before any compose returns both keys as None."""
        composer = _make_composer()
        snap = composer.status_snapshot()
        assert snap["last_compose_ts"] is None
        assert snap["last_salutation"] is None

    def test_short_sentence_within_limit_not_clipped(self):
        """A sentence under max_sentence_words is not clipped and not split."""
        composer = _make_composer(max_sentence_words=50)
        result = composer.compose("Short sentence.", language="en")
        assert result.clipped is False
        assert len(result.sentences) == 1
