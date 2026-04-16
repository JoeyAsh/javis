"""BackchannelPlayer: Play subtle acknowledgments during long user turns.

Low-volume "mhm", "right", etc. during natural pauses in user speech,
making JARVIS feel more engaged and human-like.

Example usage:
    from audio.backchannels import BackchannelPlayer

    player = BackchannelPlayer(audio_player, cache_dir)

    # During user speech, check for pause opportunities
    if silence_duration > 1.2:
        await player.maybe_play(silence_duration, "en")
"""

from __future__ import annotations

import random
import time
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from utils.logger import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger("backchannels")

# Backchannel phrases by language
BACKCHANNEL_PHRASES = {
    "de": ["mhm", "ja", "ok", "verstehe"],
    "en": ["mhm", "right", "ok", "I see"],
}


class AudioPlayerProtocol(Protocol):
    """Protocol for audio player."""

    async def play(self, audio_path: Path | bytes, volume: float = 1.0, **kwargs) -> None:
        """Play audio at specified volume."""
        ...


class BackchannelPlayer:
    """Play subtle acknowledgments during long user turns.

    Plays low-volume backchannels during natural pauses in user speech,
    respecting a minimum interval between plays.

    Attributes:
        last_play_time: Unix timestamp of last backchannel.
    """

    def __init__(
        self,
        audio_player: AudioPlayerProtocol,
        cache_dir: Path | str,
        silence_threshold_ms: int = 1200,
        volume: float = 0.3,
        min_interval_seconds: float = 3.0,
    ) -> None:
        """Initialize backchannel player.

        Args:
            audio_player: Audio player for playback.
            cache_dir: Directory containing cached audio files.
            silence_threshold_ms: Minimum silence duration to trigger (default: 1200).
            volume: Playback volume 0-1 (default: 0.3 = 30%).
            min_interval_seconds: Minimum seconds between backchannels (default: 3).
        """
        self._player = audio_player
        self._cache_dir = Path(cache_dir)
        self._silence_threshold = silence_threshold_ms / 1000
        self._volume = volume
        self._min_interval = min_interval_seconds
        self._last_backchannel = 0.0

    @property
    def last_play_time(self) -> float:
        """Return timestamp of last backchannel play."""
        return self._last_backchannel

    async def maybe_play(
        self,
        silence_duration: float,
        language: str,
    ) -> bool:
        """Maybe play a backchannel if conditions are met.

        Conditions:
        1. Silence duration exceeds threshold
        2. Minimum interval since last backchannel has passed

        Args:
            silence_duration: Duration of current silence in seconds.
            language: Language code for phrase selection.

        Returns:
            True if backchannel was played.
        """
        now = time.time()

        # Check conditions
        if silence_duration < self._silence_threshold:
            return False

        if now - self._last_backchannel < self._min_interval:
            return False

        # Select and play
        phrases = BACKCHANNEL_PHRASES.get(language, BACKCHANNEL_PHRASES["en"])
        phrase = random.choice(phrases)

        # Build filename: backchannel_en_mhm.wav
        filename = f"backchannel_{language}_{phrase.lower().replace(' ', '_')}.wav"
        audio_path = self._cache_dir / filename

        if audio_path.exists():
            logger.debug(f"Playing backchannel: {phrase}")
            try:
                await self._player.play(audio_path, volume=self._volume)
                self._last_backchannel = now
                return True
            except Exception as e:
                logger.error(f"Failed to play backchannel: {e}")
                return False
        else:
            logger.debug(f"Backchannel audio not found: {audio_path}")
            return False

    def reset_timer(self) -> None:
        """Reset the interval timer.

        Call this at the start of a new conversation turn.
        """
        self._last_backchannel = 0.0

    def get_phrases(self, language: str) -> list[str]:
        """Get available backchannel phrases for a language.

        Args:
            language: Language code.

        Returns:
            List of phrase strings.
        """
        return BACKCHANNEL_PHRASES.get(language, BACKCHANNEL_PHRASES["en"])
