"""Unit tests for StreamSplitter.

Tests cover:
- Sentence boundary detection
- Streaming token processing
- Buffer management
- Static text splitting
"""

import asyncio

import pytest

from audio.stream_splitter import StreamSplitter


class TestStreamSplitter:
    """Tests for StreamSplitter class."""

    def test_init_with_defaults(self):
        """Test initialization with default values."""
        splitter = StreamSplitter()

        assert splitter._min_chars == 20
        assert splitter._max_wait_ms == 500
        assert splitter.buffer_length == 0

    def test_init_with_custom_values(self):
        """Test initialization with custom values."""
        splitter = StreamSplitter(min_chars=10, max_wait_ms=1000)

        assert splitter._min_chars == 10
        assert splitter._max_wait_ms == 1000

    def test_reset_clears_buffer(self):
        """Test that reset clears the buffer."""
        splitter = StreamSplitter()
        splitter._buffer = "Some content"

        splitter.reset()

        assert splitter.buffer_length == 0


class TestSplitText:
    """Tests for static text splitting."""

    def test_split_single_sentence(self):
        """Test splitting a single sentence."""
        splitter = StreamSplitter()

        result = splitter.split_text("Hello, Sir.")

        assert result == ["Hello, Sir."]

    def test_split_multiple_sentences(self):
        """Test splitting multiple sentences."""
        splitter = StreamSplitter()

        result = splitter.split_text("Hello, Sir. How are you? I hope well.")

        assert len(result) == 3
        assert result[0] == "Hello, Sir."
        assert result[1] == "How are you?"
        assert result[2] == "I hope well."

    def test_split_preserves_exclamation(self):
        """Test that exclamation marks are handled."""
        splitter = StreamSplitter()

        result = splitter.split_text("Warning! That's dangerous.")

        assert len(result) == 2
        assert result[0] == "Warning!"

    def test_split_handles_no_punctuation(self):
        """Test text without sentence-ending punctuation."""
        splitter = StreamSplitter()

        result = splitter.split_text("No punctuation here")

        assert result == ["No punctuation here"]

    def test_split_handles_empty_string(self):
        """Test empty string input."""
        splitter = StreamSplitter()

        result = splitter.split_text("")

        assert result == []


class TestStreamProcessing:
    """Tests for streaming token processing."""

    @pytest.mark.asyncio
    async def test_process_yields_complete_sentences(self):
        """Test that complete sentences are yielded."""
        splitter = StreamSplitter(min_chars=10)

        async def token_stream():
            tokens = ["Hello, ", "Sir. ", "How are ", "you?"]
            for token in tokens:
                yield token

        sentences = []
        async for sentence in splitter.process(token_stream()):
            sentences.append(sentence)

        assert len(sentences) == 2
        assert "Hello, Sir." in sentences[0]
        assert "How are you?" in sentences[1]

    @pytest.mark.asyncio
    async def test_process_handles_single_token(self):
        """Test processing a single token."""
        splitter = StreamSplitter(min_chars=5)

        async def token_stream():
            yield "Hello."

        sentences = []
        async for sentence in splitter.process(token_stream()):
            sentences.append(sentence)

        assert sentences == ["Hello."]

    @pytest.mark.asyncio
    async def test_process_flushes_buffer_at_end(self):
        """Test that remaining buffer is flushed."""
        splitter = StreamSplitter(min_chars=100)  # High threshold

        async def token_stream():
            yield "Short text"

        sentences = []
        async for sentence in splitter.process(token_stream()):
            sentences.append(sentence)

        assert sentences == ["Short text"]

    @pytest.mark.asyncio
    async def test_process_handles_german_umlauts(self):
        """Test handling of German umlauts in sentence boundaries."""
        splitter = StreamSplitter(min_chars=10)

        async def token_stream():
            yield "Guten Tag. Über das Wetter."

        sentences = []
        async for sentence in splitter.process(token_stream()):
            sentences.append(sentence)

        assert len(sentences) == 2
        assert "Guten Tag." in sentences[0]
        assert "Über" in sentences[1]

    @pytest.mark.asyncio
    async def test_process_resets_buffer(self):
        """Test that buffer is reset after processing."""
        splitter = StreamSplitter()
        splitter._buffer = "leftover"

        async def token_stream():
            yield "New text."

        async for _ in splitter.process(token_stream()):
            pass

        assert splitter.buffer_length == 0
