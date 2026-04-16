"""BargeInDetector: Detect user speech during TTS playback.

Enables natural conversation flow by detecting when the user starts
speaking while JARVIS is still talking, and immediately stopping playback.

Target: <150ms from speech detection to TTS silence.

Example usage:
    from audio.barge_in import BargeInDetector

    detector = BargeInDetector(
        vad=vad_detector,
        tts_pipeline=pipeline,
        on_barge_in=handle_barge_in,
    )

    await detector.start_monitoring()
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Awaitable, Callable, Protocol

from utils.logger import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger("barge_in")


class VADProtocol(Protocol):
    """Protocol for Voice Activity Detector."""

    async def is_speech(self) -> bool:
        """Check if current audio contains speech."""
        ...


class TTSPipelineProtocol(Protocol):
    """Protocol for TTS pipeline."""

    @property
    def is_playing(self) -> bool:
        """Check if currently playing."""
        ...

    def cancel(self) -> None:
        """Cancel playback."""
        ...


class BargeInDetector:
    """Detect user speech during TTS playback and trigger interruption.

    Monitors VAD during TTS playback. When sustained speech is detected
    (exceeding sensitivity threshold), cancels TTS and invokes callback.

    Attributes:
        is_monitoring: Whether currently monitoring for barge-in.
    """

    def __init__(
        self,
        vad: VADProtocol,
        tts_pipeline: TTSPipelineProtocol,
        on_barge_in: Callable[[], Awaitable[None]],
        sensitivity_ms: int = 150,
        poll_interval_ms: int = 50,
    ) -> None:
        """Initialize barge-in detector.

        Args:
            vad: Voice Activity Detector instance.
            tts_pipeline: TTS pipeline to cancel on barge-in.
            on_barge_in: Async callback when barge-in detected.
            sensitivity_ms: Minimum speech duration to trigger (default: 150ms).
            poll_interval_ms: VAD polling interval (default: 50ms).
        """
        self._vad = vad
        self._tts = tts_pipeline
        self._on_barge_in = on_barge_in
        self._sensitivity_ms = sensitivity_ms
        self._poll_interval_s = poll_interval_ms / 1000
        self._monitoring = False
        self._monitor_task: asyncio.Task | None = None

    @property
    def is_monitoring(self) -> bool:
        """Check if monitoring is active."""
        return self._monitoring

    async def start_monitoring(self) -> None:
        """Start monitoring for user speech during TTS.

        Blocks until TTS playback ends or barge-in is detected.
        Safe to call multiple times - will not start duplicate monitors.
        """
        if self._monitoring:
            logger.debug("Already monitoring for barge-in")
            return

        self._monitoring = True
        speech_start: float | None = None

        logger.debug("Starting barge-in monitoring")

        try:
            while self._monitoring and self._tts.is_playing:
                is_speech = await self._vad.is_speech()

                if is_speech:
                    if speech_start is None:
                        speech_start = asyncio.get_event_loop().time()
                    else:
                        duration_ms = (
                            asyncio.get_event_loop().time() - speech_start
                        ) * 1000

                        if duration_ms >= self._sensitivity_ms:
                            # Barge-in detected
                            logger.info(
                                f"Barge-in detected after {duration_ms:.0f}ms of speech"
                            )
                            await self._handle_barge_in()
                            return
                else:
                    # Reset speech timer on silence
                    speech_start = None

                await asyncio.sleep(self._poll_interval_s)

        except asyncio.CancelledError:
            logger.debug("Barge-in monitoring cancelled")
            raise
        finally:
            self._monitoring = False

    async def start_monitoring_background(self) -> None:
        """Start monitoring in background task.

        Non-blocking alternative to start_monitoring().
        Use stop_monitoring() to cancel.
        """
        if self._monitor_task and not self._monitor_task.done():
            return

        self._monitor_task = asyncio.create_task(self.start_monitoring())

    async def _handle_barge_in(self) -> None:
        """Handle barge-in: cancel TTS, notify system.

        Target: <150ms from detection to silence.
        """
        # Cancel TTS immediately
        self._tts.cancel()
        self._monitoring = False

        # Invoke callback
        try:
            await self._on_barge_in()
        except Exception as e:
            logger.error(f"Barge-in callback error: {e}")

    def stop_monitoring(self) -> None:
        """Stop monitoring for barge-in."""
        self._monitoring = False

        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()


class SimpleVAD:
    """Simple VAD based on RMS amplitude threshold.

    For production use, consider using webrtcvad or silero-vad.
    """

    def __init__(
        self,
        threshold: float = 0.02,
        get_audio_chunk: Callable[[], Awaitable[bytes | None]] | None = None,
    ) -> None:
        """Initialize simple VAD.

        Args:
            threshold: RMS threshold for speech detection (0-1 scale).
            get_audio_chunk: Async function to get current audio chunk.
        """
        self._threshold = threshold
        self._get_audio_chunk = get_audio_chunk
        self._last_rms: float = 0.0

    async def is_speech(self) -> bool:
        """Check if current audio contains speech.

        Returns:
            True if RMS exceeds threshold.
        """
        if self._get_audio_chunk is None:
            return False

        chunk = await self._get_audio_chunk()
        if chunk is None or len(chunk) == 0:
            return False

        # Calculate RMS
        import numpy as np

        audio = np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0
        rms = float(np.sqrt(np.mean(audio**2)))
        self._last_rms = rms

        return rms > self._threshold

    @property
    def last_rms(self) -> float:
        """Return last computed RMS value."""
        return self._last_rms
