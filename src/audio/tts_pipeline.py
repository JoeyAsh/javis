"""TTSPipeline: Streaming TTS pipeline with sentence overlap.

Enables low-latency voice output by:
1. Starting TTS synthesis on first complete sentence
2. Queuing subsequent sentences while playing
3. Supporting barge-in cancellation

Example usage:
    from audio.tts_pipeline import TTSPipeline

    pipeline = TTSPipeline(tts_client, audio_player)

    async for sentence in stream_splitter.process(tokens):
        await pipeline.queue_sentence(sentence, voice_id)

    await pipeline.finish()
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Protocol

from utils.logger import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = get_logger("tts_pipeline")


class TTSClientProtocol(Protocol):
    """Protocol for TTS client."""

    async def synthesize(self, text: str, **kwargs) -> bytes:
        """Synthesize text to audio bytes."""
        ...


class AudioPlayerProtocol(Protocol):
    """Protocol for audio player."""

    async def play(self, audio: bytes) -> None:
        """Play audio bytes."""
        ...

    def stop(self) -> None:
        """Stop playback immediately."""
        ...


class TTSPipeline:
    """Pipeline streaming sentences to TTS with overlap.

    Manages a queue of sentences for TTS synthesis and playback,
    allowing new sentences to be synthesized while previous ones play.

    Attributes:
        is_playing: Whether audio is currently playing.
        is_cancelled: Whether pipeline has been cancelled.
    """

    def __init__(
        self,
        tts_client: TTSClientProtocol,
        audio_player: AudioPlayerProtocol,
        queue_size: int = 3,
    ) -> None:
        """Initialize TTS pipeline.

        Args:
            tts_client: TTS client for synthesis.
            audio_player: Audio player for playback.
            queue_size: Maximum sentences to queue ahead.
        """
        self._tts = tts_client
        self._player = audio_player
        self._queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=queue_size)
        self._playing = False
        self._cancelled = False
        self._playback_task: asyncio.Task | None = None
        self._voice_id: str | None = None

    @property
    def is_playing(self) -> bool:
        """Check if currently playing audio."""
        return self._playing and not self._cancelled

    @property
    def is_cancelled(self) -> bool:
        """Check if pipeline is cancelled."""
        return self._cancelled

    async def stream_sentences(
        self,
        sentences: AsyncIterator[str],
        voice_id: str,
        **tts_kwargs,
    ) -> None:
        """Stream sentences through TTS to audio output.

        Starts playback on first sentence while generating subsequent ones.
        Supports cancellation via the cancel() method.

        Args:
            sentences: Async iterator of sentences.
            voice_id: Voice ID for TTS synthesis.
            **tts_kwargs: Additional arguments for TTS client.
        """
        self._cancelled = False
        self._voice_id = voice_id

        # Start playback consumer
        self._playback_task = asyncio.create_task(self._playback_loop())

        try:
            async for sentence in sentences:
                if self._cancelled:
                    logger.debug("Pipeline cancelled, stopping sentence processing")
                    break

                # Generate TTS for sentence
                logger.debug(f"Synthesizing: {sentence[:50]}...")
                try:
                    audio = await self._tts.synthesize(
                        text=sentence,
                        voice_id=voice_id,
                        **tts_kwargs,
                    )
                    # Queue for playback
                    await self._queue.put(audio)
                except Exception as e:
                    logger.error(f"TTS synthesis failed: {e}")
                    continue

            # Signal end of stream
            await self._queue.put(None)

            # Wait for playback to complete
            if self._playback_task:
                await self._playback_task

        except asyncio.CancelledError:
            self._cancelled = True
            await self._queue.put(None)
            raise
        finally:
            self._playback_task = None

    async def queue_sentence(
        self,
        sentence: str,
        voice_id: str | None = None,
        **tts_kwargs,
    ) -> bool:
        """Queue a single sentence for TTS and playback.

        Args:
            sentence: Text to synthesize.
            voice_id: Voice ID (uses last voice_id if None).
            **tts_kwargs: Additional arguments for TTS client.

        Returns:
            True if queued successfully, False if cancelled.
        """
        if self._cancelled:
            return False

        vid = voice_id or self._voice_id
        if not vid:
            logger.warning("No voice_id specified")
            return False

        try:
            audio = await self._tts.synthesize(
                text=sentence,
                voice_id=vid,
                **tts_kwargs,
            )
            await self._queue.put(audio)
            return True
        except Exception as e:
            logger.error(f"TTS synthesis failed: {e}")
            return False

    async def start_playback(self) -> None:
        """Start the playback consumer task.

        Call this before queuing sentences if not using stream_sentences().
        """
        if self._playback_task is None or self._playback_task.done():
            self._cancelled = False
            self._playback_task = asyncio.create_task(self._playback_loop())

    async def finish(self) -> None:
        """Signal end of stream and wait for playback to complete."""
        await self._queue.put(None)
        if self._playback_task:
            await self._playback_task

    async def _playback_loop(self) -> None:
        """Consume audio queue and play."""
        while True:
            try:
                audio = await self._queue.get()

                if audio is None:
                    logger.debug("Playback loop received end signal")
                    break

                if self._cancelled:
                    continue

                self._playing = True
                logger.debug(f"Playing audio ({len(audio)} bytes)")

                try:
                    await self._player.play(audio)
                except Exception as e:
                    logger.error(f"Playback error: {e}")
                finally:
                    self._playing = False

            except asyncio.CancelledError:
                break

    def cancel(self) -> None:
        """Cancel playback immediately (barge-in).

        Stops current playback and clears the queue.
        """
        logger.info("Pipeline cancelled (barge-in)")
        self._cancelled = True
        self._player.stop()

        # Clear queue
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    def reset(self) -> None:
        """Reset pipeline state for reuse."""
        self._cancelled = False
        self._playing = False
        self._voice_id = None

        # Clear queue
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break
