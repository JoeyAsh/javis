"""FillerPlayer: Play thinking fillers when response is delayed.

Plays a short neutral filler if agent response exceeds the delay threshold,
masking processing latency and making JARVIS feel more responsive.

Example usage:
    from audio.fillers import FillerPlayer

    filler = FillerPlayer(audio_player, cache_dir)

    # Start waiting for response
    response_event = asyncio.Event()

    # This will play filler if response takes >800ms
    await filler.wait_for_response_or_filler(response_event, "en")

    # Elsewhere, when response arrives:
    response_event.set()
"""

from __future__ import annotations

import asyncio
import random
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from utils.logger import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger("fillers")

# Filler phrases by language
FILLER_PHRASES = {
    "de": ["Moment", "Einen Augenblick", "Lassen Sie mich sehen"],
    "en": ["One moment", "Let me see", "Just a moment"],
}


class AudioPlayerProtocol(Protocol):
    """Protocol for audio player."""

    async def play(self, audio_path: Path | bytes, **kwargs) -> None:
        """Play audio."""
        ...


class FillerPlayer:
    """Play thinking fillers when response is delayed.

    Uses pre-cached audio files for minimal latency.

    Attributes:
        filler_played: Whether a filler was played in last wait.
    """

    def __init__(
        self,
        audio_player: AudioPlayerProtocol,
        cache_dir: Path | str,
        delay_threshold_ms: int = 800,
    ) -> None:
        """Initialize filler player.

        Args:
            audio_player: Audio player for playback.
            cache_dir: Directory containing cached filler audio files.
            delay_threshold_ms: Ms to wait before playing filler (default: 800).
        """
        self._player = audio_player
        self._cache_dir = Path(cache_dir)
        self._delay_threshold = delay_threshold_ms / 1000
        self._played = False

    @property
    def filler_played(self) -> bool:
        """Check if filler was played in last wait."""
        return self._played

    async def wait_for_response_or_filler(
        self,
        response_event: asyncio.Event,
        language: str,
    ) -> None:
        """Wait for response; play filler if delayed.

        Blocks until either:
        1. response_event is set (response arrived), or
        2. delay_threshold exceeded and filler is played

        Args:
            response_event: Event that fires when response starts.
            language: Language for filler phrase.
        """
        self._played = False

        try:
            await asyncio.wait_for(
                response_event.wait(),
                timeout=self._delay_threshold,
            )
            # Response arrived in time
            logger.debug("Response arrived before filler threshold")
        except asyncio.TimeoutError:
            # Response delayed, play filler
            await self._play_filler(language)

    async def _play_filler(self, language: str) -> None:
        """Play a random filler phrase.

        Args:
            language: Language code for phrase selection.
        """
        phrases = FILLER_PHRASES.get(language, FILLER_PHRASES["en"])
        phrase = random.choice(phrases)

        # Build filename: filler_en_one_moment.wav
        filename = f"filler_{language}_{phrase.lower().replace(' ', '_')}.wav"
        audio_path = self._cache_dir / filename

        if audio_path.exists():
            logger.debug(f"Playing filler: {phrase}")
            try:
                await self._player.play(audio_path)
                self._played = True
            except Exception as e:
                logger.error(f"Failed to play filler: {e}")
        else:
            logger.debug(f"Filler audio not found: {audio_path}")

    async def play_random_filler(self, language: str) -> bool:
        """Play a random filler immediately.

        Args:
            language: Language code for phrase selection.

        Returns:
            True if filler was played.
        """
        await self._play_filler(language)
        return self._played

    def get_filler_phrases(self, language: str) -> list[str]:
        """Get available filler phrases for a language.

        Args:
            language: Language code.

        Returns:
            List of filler phrase strings.
        """
        return FILLER_PHRASES.get(language, FILLER_PHRASES["en"])
