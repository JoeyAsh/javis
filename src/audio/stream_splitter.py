"""StreamSplitter: Split streaming LLM output into sentences for TTS pipelining.

Enables first-audio-output before full response completes by detecting
sentence boundaries and yielding complete sentences for immediate TTS synthesis.

Example usage:
    from audio.stream_splitter import StreamSplitter

    splitter = StreamSplitter()

    async def process_response():
        async for sentence in splitter.process(token_stream):
            audio = await tts.synthesize(sentence)
            await player.play(audio)
"""

from __future__ import annotations

import asyncio
import re
from typing import AsyncIterator

from utils.logger import get_logger

logger = get_logger("stream_splitter")

# Regex for sentence boundaries
# Matches period, exclamation, or question mark followed by whitespace and capital letter
# or at end of string
SENTENCE_ENDINGS = re.compile(r"(?<=[.!?])\s+(?=[A-ZÄÖÜ])|(?<=[.!?])$")


class StreamSplitter:
    """Split streaming LLM output into sentences for TTS pipelining.

    Buffers incoming tokens and yields complete sentences when detected.
    Uses sentence-ending punctuation followed by capital letters as boundaries.

    Attributes:
        min_chars: Minimum characters before attempting split.
        max_wait_ms: Maximum ms to wait for sentence completion.
    """

    def __init__(self, min_chars: int = 20, max_wait_ms: int = 500) -> None:
        """Initialize splitter.

        Args:
            min_chars: Minimum characters before attempting split.
            max_wait_ms: Maximum ms to wait for sentence completion before
                flushing the buffer anyway.
        """
        self._min_chars = min_chars
        self._max_wait_ms = max_wait_ms
        self._buffer = ""

    @property
    def buffer_length(self) -> int:
        """Return current buffer length."""
        return len(self._buffer)

    def reset(self) -> None:
        """Clear the internal buffer."""
        self._buffer = ""

    async def process(
        self,
        token_stream: AsyncIterator[str],
    ) -> AsyncIterator[str]:
        """Process token stream and yield complete sentences.

        Yields sentences as soon as sentence boundaries are detected,
        allowing TTS to start before the full response is complete.

        Args:
            token_stream: Async iterator of LLM tokens.

        Yields:
            Complete sentences ready for TTS.
        """
        self._buffer = ""
        last_yield_time = asyncio.get_running_loop().time()

        async for token in token_stream:
            self._buffer += token

            # Check for sentence boundary when we have enough content
            if len(self._buffer) >= self._min_chars:
                match = SENTENCE_ENDINGS.search(self._buffer)
                if match:
                    sentence = self._buffer[: match.end()].strip()
                    self._buffer = self._buffer[match.end() :].lstrip()

                    if sentence:
                        logger.debug(f"Yielding sentence ({len(sentence)} chars)")
                        yield sentence
                        last_yield_time = asyncio.get_running_loop().time()

            # Check for max wait timeout
            current_time = asyncio.get_running_loop().time()
            elapsed_ms = (current_time - last_yield_time) * 1000

            if elapsed_ms > self._max_wait_ms and len(self._buffer) > self._min_chars:
                # Force flush on timeout
                logger.debug(f"Timeout flush ({len(self._buffer)} chars)")
                yield self._buffer.strip()
                self._buffer = ""
                last_yield_time = current_time

        # Yield remaining buffer
        if self._buffer.strip():
            logger.debug(f"Final flush ({len(self._buffer)} chars)")
            yield self._buffer.strip()

        self._buffer = ""

    def split_text(self, text: str) -> list[str]:
        """Split static text into sentences (non-streaming).

        Useful for pre-processing text before TTS.

        Args:
            text: Full text to split.

        Returns:
            List of sentence strings.
        """
        sentences = []
        remaining = text

        while remaining:
            remaining = remaining.strip()
            if not remaining:
                break

            match = SENTENCE_ENDINGS.search(remaining)
            if match:
                sentence = remaining[: match.end()].strip()
                remaining = remaining[match.end() :]
                if sentence:
                    sentences.append(sentence)
            else:
                # No more boundaries, add remainder
                sentences.append(remaining)
                break

        return sentences
