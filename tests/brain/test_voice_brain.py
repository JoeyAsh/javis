"""Unit tests for voice-related brain modules.

Tests cover:
- QuickAckGenerator
- ResponseLengthController
- ResponseCache
"""

import tempfile
from pathlib import Path

import pytest

from brain.quick_ack import QuickAckGenerator
from brain.response_cache import ResponseCache
from brain.response_length import ResponseFormatter, ResponseLengthController


class TestQuickAckGenerator:
    """Tests for QuickAckGenerator."""

    @pytest.fixture
    def temp_cache_dir(self):
        """Provide temporary cache directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_should_ack_explain_query(self, temp_cache_dir):
        """Test that 'explain' queries trigger ack."""
        ack_gen = QuickAckGenerator(temp_cache_dir)

        assert ack_gen.should_ack("Can you explain how this works?") is True
        assert ack_gen.should_ack("Explain the concept of AI") is True

    def test_should_ack_multiple_questions(self, temp_cache_dir):
        """Test that multiple questions trigger ack."""
        ack_gen = QuickAckGenerator(temp_cache_dir)

        assert ack_gen.should_ack("What time is it? And what's the weather?") is True

    def test_should_ack_german_query(self, temp_cache_dir):
        """Test German complexity patterns."""
        ack_gen = QuickAckGenerator(temp_cache_dir)

        assert ack_gen.should_ack("Kannst du mir das erklären?") is True
        assert ack_gen.should_ack("Wie funktioniert das?") is True

    def test_should_not_ack_simple_query(self, temp_cache_dir):
        """Test that simple queries don't trigger ack."""
        ack_gen = QuickAckGenerator(temp_cache_dir)

        assert ack_gen.should_ack("What time is it?") is False
        assert ack_gen.should_ack("Turn on the lights") is False

    def test_get_ack_returns_phrase_and_path(self, temp_cache_dir):
        """Test get_ack returns phrase and path."""
        ack_gen = QuickAckGenerator(temp_cache_dir)

        phrase, path = ack_gen.get_ack("en")

        assert phrase in ["Right", "Got it", "Sure", "Yes"]
        assert path.suffix == ".wav"
        assert "ack_en" in path.name

    def test_get_phrases(self, temp_cache_dir):
        """Test getting available phrases."""
        ack_gen = QuickAckGenerator(temp_cache_dir)

        en_phrases = ack_gen.get_phrases("en")
        de_phrases = ack_gen.get_phrases("de")

        assert "Right" in en_phrases
        assert "Klar" in de_phrases


class TestResponseLengthController:
    """Tests for ResponseLengthController."""

    def test_default_is_not_detail_mode(self):
        """Test default mode is not detail."""
        controller = ResponseLengthController()

        assert controller.detail_mode is False

    def test_check_detail_request_english(self):
        """Test English detail request detection."""
        controller = ResponseLengthController()

        assert controller.check_detail_request("Tell me more about that") is True
        assert controller.detail_mode is True

    def test_check_detail_request_german(self):
        """Test German detail request detection."""
        controller = ResponseLengthController()

        assert controller.check_detail_request("Erklär mir mehr") is True
        assert controller.detail_mode is True

    def test_check_detail_request_not_triggered(self):
        """Test that normal queries don't trigger detail mode."""
        controller = ResponseLengthController()

        assert controller.check_detail_request("What's the weather?") is False
        assert controller.detail_mode is False

    def test_get_length_modifier_default(self):
        """Test length modifier in default mode."""
        controller = ResponseLengthController()

        modifier = controller.get_length_modifier()

        assert "2 sentences" in modifier
        assert len(modifier) > 0

    def test_get_length_modifier_detail_mode(self):
        """Test length modifier in detail mode."""
        controller = ResponseLengthController()
        controller.check_detail_request("Tell me more")

        modifier = controller.get_length_modifier()

        assert modifier == ""

    def test_reset(self):
        """Test reset to default mode."""
        controller = ResponseLengthController()
        controller.check_detail_request("Tell me more")

        controller.reset()

        assert controller.detail_mode is False


class TestResponseFormatter:
    """Tests for ResponseFormatter."""

    def test_format_removes_markdown(self):
        """Test markdown removal."""
        formatter = ResponseFormatter()

        result = formatter.format_for_speech("**Bold** and *italic*")

        assert "**" not in result
        assert "*" not in result
        assert "Bold" in result

    def test_format_removes_code_blocks(self):
        """Test code block removal."""
        formatter = ResponseFormatter()

        result = formatter.format_for_speech("Here's code: ```python\nprint('hi')```")

        assert "```" not in result
        assert "python" not in result

    def test_format_removes_links(self):
        """Test link removal preserves text."""
        formatter = ResponseFormatter()

        result = formatter.format_for_speech("Check [this link](http://example.com)")

        assert "[" not in result
        assert "http" not in result
        assert "this link" in result

    def test_truncate_sentences(self):
        """Test sentence truncation."""
        formatter = ResponseFormatter()

        result = formatter.truncate_sentences(
            "First. Second. Third. Fourth. Fifth.",
            max_sentences=2,
        )

        assert "First." in result
        assert "Second." in result
        assert "Third" not in result


class TestResponseCache:
    """Tests for ResponseCache."""

    def test_set_and_get(self):
        """Test setting and getting cached response."""
        cache = ResponseCache(max_size=10, ttl_seconds=60)

        cache.set("time_query", {}, "It's 3 PM, Sir.")

        result = cache.get("time_query", {})

        assert result == "It's 3 PM, Sir."

    def test_get_returns_none_for_missing(self):
        """Test get returns None for missing key."""
        cache = ResponseCache()

        result = cache.get("nonexistent", {})

        assert result is None

    def test_get_returns_none_for_expired(self):
        """Test get returns None for expired entry."""
        cache = ResponseCache(ttl_seconds=0)  # Immediate expiration

        cache.set("test", {}, "Response")

        result = cache.get("test", {})

        assert result is None

    def test_lru_eviction(self):
        """Test LRU eviction when max size exceeded."""
        cache = ResponseCache(max_size=2)

        cache.set("first", {}, "First")
        cache.set("second", {}, "Second")
        cache.set("third", {}, "Third")  # Should evict "first"

        assert cache.get("first", {}) is None
        assert cache.get("second", {}) is not None
        assert cache.get("third", {}) is not None

    def test_hit_rate_tracking(self):
        """Test hit rate tracking."""
        cache = ResponseCache()

        cache.set("test", {}, "Response")
        cache.get("test", {})  # Hit
        cache.get("test", {})  # Hit
        cache.get("missing", {})  # Miss

        assert cache.hit_count == 2
        assert cache.miss_count == 1
        assert cache.hit_rate == pytest.approx(2 / 3)

    def test_invalidate(self):
        """Test invalidating cache entry."""
        cache = ResponseCache()

        cache.set("test", {}, "Response")
        result = cache.invalidate("test", {})

        assert result is True
        assert cache.get("test", {}) is None

    def test_clear(self):
        """Test clearing all entries."""
        cache = ResponseCache()

        cache.set("test1", {}, "R1")
        cache.set("test2", {}, "R2")

        count = cache.clear()

        assert count == 2
        assert cache.size == 0

    def test_get_stats(self):
        """Test getting cache statistics."""
        cache = ResponseCache(max_size=100, ttl_seconds=60)

        cache.set("test", {}, "Response")
        cache.get("test", {})

        stats = cache.get_stats()

        assert stats["size"] == 1
        assert stats["max_size"] == 100
        assert stats["hit_count"] == 1
        assert stats["ttl_seconds"] == 60

    def test_params_affect_cache_key(self):
        """Test that different params create different keys."""
        cache = ResponseCache()

        cache.set("query", {"format": "12h"}, "3 PM")
        cache.set("query", {"format": "24h"}, "15:00")

        assert cache.get("query", {"format": "12h"}) == "3 PM"
        assert cache.get("query", {"format": "24h"}) == "15:00"
