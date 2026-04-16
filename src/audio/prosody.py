"""Prosody configuration for JARVIS TTS.

Context-aware voice settings that adjust based on:
- Time of day (morning energy, night calm)
- Error context (serious tone)
- User activity state

Example usage:
    from audio.prosody import get_voice_mood, get_fish_audio_params

    mood = get_voice_mood(orb_state="speaking", error_context=False)
    params = get_fish_audio_params(mood)

    audio = await tts.synthesize(text, **params)
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from utils.logger import get_logger

logger = get_logger("prosody")


class VoiceMood(Enum):
    """Voice mood states for TTS prosody."""

    CALM = "calm"  # Night time, relaxed
    BRIGHT = "bright"  # Morning, energetic
    SERIOUS = "serious"  # Error context, urgent
    NEUTRAL = "neutral"  # Default state


def get_voice_mood(
    orb_state: str = "idle",
    hour: int | None = None,
    error_context: bool = False,
) -> VoiceMood:
    """Determine voice mood based on context.

    Priority order:
    1. Error context overrides all
    2. Time-based mood if no special context

    Args:
        orb_state: Current orb visualization state.
        hour: Hour of day (0-23), or None for current time.
        error_context: Whether responding to an error.

    Returns:
        Appropriate VoiceMood for the context.
    """
    # Error context overrides everything
    if error_context:
        return VoiceMood.SERIOUS

    # Get current hour if not provided
    if hour is None:
        hour = datetime.now().hour

    # Time-based mood selection
    if 6 <= hour < 10:
        return VoiceMood.BRIGHT  # Morning energy
    elif 22 <= hour or hour < 6:
        return VoiceMood.CALM  # Night calm
    else:
        return VoiceMood.NEUTRAL


def get_fish_audio_params(mood: VoiceMood) -> dict:
    """Map mood to Fish Audio API parameters.

    Adjusts speed, pitch, and volume based on mood for
    more natural and context-appropriate speech.

    Args:
        mood: Voice mood to map.

    Returns:
        Dictionary of Fish Audio synthesis parameters.
    """
    params = {
        VoiceMood.CALM: {
            "speed": 0.9,
            "pitch": -2,
            "volume": 0.8,
        },
        VoiceMood.BRIGHT: {
            "speed": 1.05,
            "pitch": 1,
            "volume": 1.0,
        },
        VoiceMood.SERIOUS: {
            "speed": 0.95,
            "pitch": -3,
            "volume": 0.9,
        },
        VoiceMood.NEUTRAL: {
            "speed": 1.0,
            "pitch": 0,
            "volume": 1.0,
        },
    }
    return params.get(mood, params[VoiceMood.NEUTRAL])


def get_prosody_hints(
    mood: VoiceMood,
    language: str = "en",
) -> str:
    """Get SSML-style prosody hints for TTS.

    Returns text hints that can be prepended to TTS input
    for providers that support them.

    Args:
        mood: Voice mood.
        language: Language code.

    Returns:
        Prosody hint string (may be empty).
    """
    # Fish Audio doesn't use SSML, but this function
    # is here for future TTS providers that might
    hints = {
        VoiceMood.CALM: "",
        VoiceMood.BRIGHT: "",
        VoiceMood.SERIOUS: "",
        VoiceMood.NEUTRAL: "",
    }
    return hints.get(mood, "")


class ProsodyConfig:
    """Manages prosody configuration and state.

    Tracks context for consistent mood selection across
    a conversation or session.
    """

    def __init__(self) -> None:
        """Initialize prosody config."""
        self._error_context = False
        self._override_mood: VoiceMood | None = None

    @property
    def current_mood(self) -> VoiceMood:
        """Get current mood based on state."""
        if self._override_mood:
            return self._override_mood
        return get_voice_mood(error_context=self._error_context)

    def set_error_context(self, is_error: bool) -> None:
        """Set error context flag.

        Args:
            is_error: Whether currently in error context.
        """
        self._error_context = is_error

    def set_mood_override(self, mood: VoiceMood | None) -> None:
        """Override automatic mood selection.

        Args:
            mood: Mood to force, or None to use automatic.
        """
        self._override_mood = mood

    def reset(self) -> None:
        """Reset to default state."""
        self._error_context = False
        self._override_mood = None
