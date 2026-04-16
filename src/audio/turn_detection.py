"""Turn detection for natural conversation flow.

Determines when the user has finished speaking using:
- Silence duration
- STT final flag
- Optional prosodic hints (falling pitch)

Example usage:
    from audio.turn_detection import TurnDetector, TurnDetectionConfig

    config = TurnDetectionConfig(silence_threshold_ms=800)
    detector = TurnDetector(config, vad)

    if await detector.is_turn_complete(silence_ms=900, stt_is_final=True):
        # User has finished speaking, process input
        pass
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from utils.logger import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger("turn_detection")


class VADProtocol(Protocol):
    """Protocol for Voice Activity Detector."""

    async def is_speech(self) -> bool:
        """Check if current audio contains speech."""
        ...


@dataclass
class TurnDetectionConfig:
    """Configuration for turn detection.

    Attributes:
        silence_threshold_ms: Ms of silence to indicate turn end.
        use_prosodic_hints: Whether to use pitch analysis.
        falling_pitch_threshold: Hz/ms threshold for turn-ending pitch drop.
        stt_final_silence_ms: Minimum silence after STT final flag.
    """

    silence_threshold_ms: int = 800
    use_prosodic_hints: bool = False  # Requires librosa
    falling_pitch_threshold: float = -0.15  # Hz/ms
    stt_final_silence_ms: int = 400


class TurnDetector:
    """Detect end of user turn using multiple signals.

    Combines silence detection, STT final flag, and optional
    prosodic analysis for natural turn-taking.

    Attributes:
        config: Turn detection configuration.
    """

    def __init__(
        self,
        config: TurnDetectionConfig | None = None,
        vad: VADProtocol | None = None,
    ) -> None:
        """Initialize turn detector.

        Args:
            config: Detection configuration.
            vad: Voice Activity Detector instance.
        """
        self._config = config or TurnDetectionConfig()
        self._vad = vad

    @property
    def config(self) -> TurnDetectionConfig:
        """Return configuration."""
        return self._config

    async def is_turn_complete(
        self,
        silence_duration_ms: float,
        stt_is_final: bool = False,
        pitch_slope: float | None = None,
    ) -> bool:
        """Determine if user turn is complete.

        Uses multiple signals:
        1. STT final flag with minimum silence
        2. Silence duration threshold
        3. Prosodic hints (falling pitch) if enabled

        Args:
            silence_duration_ms: Current silence duration in ms.
            stt_is_final: Whether STT flagged this as final.
            pitch_slope: Pitch slope in Hz/ms if prosodic analysis available.

        Returns:
            True if turn appears complete.
        """
        # STT final flag is strong signal (with minimum silence)
        if stt_is_final and silence_duration_ms >= self._config.stt_final_silence_ms:
            logger.debug("Turn complete: STT final with sufficient silence")
            return True

        # Pure silence threshold
        if silence_duration_ms >= self._config.silence_threshold_ms:
            logger.debug(f"Turn complete: silence threshold ({silence_duration_ms}ms)")
            return True

        # Prosodic hint: falling pitch suggests statement end
        if (
            self._config.use_prosodic_hints
            and pitch_slope is not None
            and pitch_slope < self._config.falling_pitch_threshold
            and silence_duration_ms >= self._config.stt_final_silence_ms
        ):
            logger.debug(f"Turn complete: falling pitch ({pitch_slope} Hz/ms)")
            return True

        return False

    def update_config(self, **kwargs) -> None:
        """Update configuration parameters.

        Args:
            **kwargs: Config attributes to update.
        """
        for key, value in kwargs.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)


class SpeechQueue:
    """Queue user utterances that arrive during JARVIS thinking state.

    Handles overlapping speech by queueing utterances for sequential
    processing.

    Attributes:
        pending_count: Number of pending utterances.
    """

    def __init__(self, max_queue: int = 3) -> None:
        """Initialize speech queue.

        Args:
            max_queue: Maximum utterances to queue.
        """
        from collections import deque
        import asyncio

        self._queue: deque[str] = deque(maxlen=max_queue)
        self._lock = asyncio.Lock()

    @property
    def pending_count(self) -> int:
        """Return number of pending utterances."""
        return len(self._queue)

    async def add(self, utterance: str) -> None:
        """Add utterance to queue.

        Args:
            utterance: Text to queue.
        """
        async with self._lock:
            self._queue.append(utterance)
            logger.debug(f"Queued utterance ({len(self._queue)} pending)")

    async def pop(self) -> str | None:
        """Get next queued utterance.

        Returns:
            Next utterance or None if empty.
        """
        async with self._lock:
            return self._queue.popleft() if self._queue else None

    async def has_pending(self) -> bool:
        """Check if there are pending utterances.

        Returns:
            True if queue is not empty.
        """
        async with self._lock:
            return len(self._queue) > 0

    async def clear(self) -> None:
        """Clear all pending utterances."""
        async with self._lock:
            self._queue.clear()
            logger.debug("Speech queue cleared")
