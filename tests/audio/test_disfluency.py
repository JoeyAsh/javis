"""Tests for src/audio/disfluency.py — maybe_prepend_disfluency().

Covers:
- Returns text unchanged when enabled=False.
- Returns text unchanged when random draw misses (rate 0).
- Always prepends when probability=1.0.
- Language-specific pool selection (DE vs EN).
- Empty text is returned unchanged.
- Result is a string (not None, not raising).
- Probability=0 never fires.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from audio.disfluency import maybe_prepend_disfluency, _POOLS


# ---------------------------------------------------------------------------
# Gate: disabled → no-op
# ---------------------------------------------------------------------------


def test_disabled_returns_text_unchanged() -> None:
    """When enabled=False the function is a no-op regardless of probability."""
    text = "Die Antwort lautet 42."
    result = maybe_prepend_disfluency(text, "de", enabled=False, probability=1.0)
    assert result == text


def test_disabled_en_returns_text_unchanged() -> None:
    """Disabled gate applies for English too."""
    text = "The answer is 42."
    result = maybe_prepend_disfluency(text, "en", enabled=False, probability=1.0)
    assert result == text


# ---------------------------------------------------------------------------
# Probability: 0 → never, 1 → always
# ---------------------------------------------------------------------------


def test_probability_zero_never_fires() -> None:
    """probability=0.0 means random.random() is always >= 0.0, so no prepend."""
    text = "Alles klar."
    for _ in range(20):
        result = maybe_prepend_disfluency(text, "de", enabled=True, probability=0.0)
        assert result == text


def test_probability_one_always_fires() -> None:
    """probability=1.0 means the disfluency is always prepended."""
    text = "Alles klar."
    for _ in range(10):
        result = maybe_prepend_disfluency(text, "de", enabled=True, probability=1.0)
        assert result != text
        assert result.endswith("klar.")


# ---------------------------------------------------------------------------
# Language pool
# ---------------------------------------------------------------------------


def test_de_pool_uses_german_tokens() -> None:
    """DE pool tokens are prepended for language='de'."""
    text = "Hier ist die Antwort."
    result = maybe_prepend_disfluency(text, "de", enabled=True, probability=1.0)
    de_tokens = [t.rstrip(",").lower() for t in _POOLS["de"]]
    first_word = result.split()[0].rstrip(",").lower()
    assert first_word in de_tokens, f"Expected DE token, got: {result!r}"


def test_en_pool_uses_english_tokens() -> None:
    """EN pool tokens are prepended for language='en'."""
    text = "Here is the answer."
    result = maybe_prepend_disfluency(text, "en", enabled=True, probability=1.0)
    en_tokens = [t.rstrip(",").lower() for t in _POOLS["en"]]
    first_word = result.split()[0].rstrip(",").lower()
    assert first_word in en_tokens, f"Expected EN token, got: {result!r}"


def test_unknown_language_falls_back_to_de() -> None:
    """Unknown language falls back to 'de' pool (first in _POOLS)."""
    text = "Odpowiedź brzmi 42."
    # "pl" not in _POOLS → falls back to "de".
    result = maybe_prepend_disfluency(text, "pl", enabled=True, probability=1.0)
    de_tokens = [t.rstrip(",").lower() for t in _POOLS.get("de", [])]
    first_word = result.split()[0].rstrip(",").lower()
    assert first_word in de_tokens


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_empty_text_returned_unchanged() -> None:
    """Empty string is a no-op even when enabled."""
    result = maybe_prepend_disfluency("", "de", enabled=True, probability=1.0)
    assert result == ""


def test_result_starts_with_capital_letter() -> None:
    """The prepended disfluency starts with a capital letter."""
    text = "Das stimmt."
    result = maybe_prepend_disfluency(text, "de", enabled=True, probability=1.0)
    assert result[0].isupper(), f"First char should be uppercase, got: {result!r}"


def test_original_text_first_char_lowercased() -> None:
    """After prepending, the original text's first character is lowercased."""
    text = "Das stimmt."
    result = maybe_prepend_disfluency(text, "de", enabled=True, probability=1.0)
    # The original text's leading char should appear lowercased mid-sentence.
    # Find where the comma+space separator ends.
    _, after_comma = result.split(",", 1)
    assert after_comma.strip()[0].islower(), (
        f"Original text should start lowercase after disfluency: {result!r}"
    )
