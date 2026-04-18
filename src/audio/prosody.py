"""Prosody context steering for JARVIS TTS.

Provides time-of-day aware prosody hints that are passed into
``FishTTSClient.synthesize()`` when ``voice.prosody_enabled`` is true.

The hint dict always has two keys:
- ``speed``  (float 0.8–1.2) — speaking rate multiplier.
- ``energy`` (``"calm"`` | ``"neutral"`` | ``"bright"``) — semantic tone.

``FishTTSClient`` maps ``speed`` to the Fish Audio ``speed`` request
parameter.  ``energy`` is informational; Fish Audio does not have a
direct energy/mood parameter, so it is logged once at startup and then
used only if a future TTS backend supports it.

Usage::

    from audio.prosody import get_prosody_hint

    hint = get_prosody_hint()              # uses datetime.now().hour
    hint = get_prosody_hint(hour=8)        # morning
    hint = get_prosody_hint(enabled=False) # always returns neutral hint
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TypedDict

from utils.logger import get_logger

logger = get_logger("prosody")

# ---------------------------------------------------------------------------
# Public typed hint dict
# ---------------------------------------------------------------------------


class ProsodyHint(TypedDict):
    """Typed dict returned by :func:`get_prosody_hint`."""

    speed: float
    energy: str  # "calm" | "neutral" | "bright"


# ---------------------------------------------------------------------------
# Legacy mood enum — kept for backward-compat with existing tests
# ---------------------------------------------------------------------------


class VoiceMood(Enum):
    """Voice mood states for TTS prosody."""

    CALM = "calm"
    BRIGHT = "bright"
    SERIOUS = "serious"
    NEUTRAL = "neutral"


# ---------------------------------------------------------------------------
# Time-of-day prosody table
# ---------------------------------------------------------------------------

# Maps (start_hour_inclusive, end_hour_exclusive) → (speed, energy)
_TIME_TABLE: list[tuple[tuple[int, int], float, str]] = [
    ((0, 6), 0.92, "calm"),    # Night
    ((6, 10), 1.05, "bright"),  # Morning
    ((10, 20), 1.0, "neutral"), # Day
    ((20, 24), 0.95, "calm"),  # Evening
]

_NEUTRAL_HINT: ProsodyHint = {"speed": 1.0, "energy": "neutral"}


def get_prosody_hint(
    hour: int | None = None,
    enabled: bool = True,
) -> ProsodyHint:
    """Return a prosody hint dict for the given hour of the day.

    Args:
        hour: Local hour (0–23).  When ``None`` the current wall-clock
            hour is used.
        enabled: When ``False`` the function immediately returns the
            neutral hint so existing TTS behaviour is unchanged.

    Returns:
        :class:`ProsodyHint` with ``speed`` and ``energy`` keys.
    """
    if not enabled:
        return _NEUTRAL_HINT

    if hour is None:
        hour = datetime.now().hour

    for (start, end), speed, energy in _TIME_TABLE:
        if start <= hour < end:
            return ProsodyHint(speed=speed, energy=energy)

    # Fallback (should never happen for valid hours 0–23)
    return _NEUTRAL_HINT


# ---------------------------------------------------------------------------
# Legacy helpers — preserved so existing tests pass unchanged
# ---------------------------------------------------------------------------


def get_voice_mood(
    orb_state: str = "idle",
    hour: int | None = None,
    error_context: bool = False,
) -> VoiceMood:
    """Determine voice mood based on context (legacy helper).

    Args:
        orb_state: Current orb visualization state (unused by this impl).
        hour: Hour of day (0–23), or None for current time.
        error_context: Whether responding to an error.

    Returns:
        Appropriate VoiceMood for the context.
    """
    if error_context:
        return VoiceMood.SERIOUS

    if hour is None:
        hour = datetime.now().hour

    if 6 <= hour < 10:
        return VoiceMood.BRIGHT
    if 22 <= hour or hour < 6:
        return VoiceMood.CALM
    return VoiceMood.NEUTRAL


def get_fish_audio_params(mood: VoiceMood) -> dict:
    """Map mood to Fish Audio API parameters (legacy helper).

    Args:
        mood: Voice mood to map.

    Returns:
        Dictionary of Fish Audio synthesis parameters.
    """
    params: dict[VoiceMood, dict] = {
        VoiceMood.CALM: {"speed": 0.9, "pitch": -2, "volume": 0.8},
        VoiceMood.BRIGHT: {"speed": 1.05, "pitch": 1, "volume": 1.0},
        VoiceMood.SERIOUS: {"speed": 0.95, "pitch": -3, "volume": 0.9},
        VoiceMood.NEUTRAL: {"speed": 1.0, "pitch": 0, "volume": 1.0},
    }
    return params.get(mood, params[VoiceMood.NEUTRAL])


def get_prosody_hints(mood: VoiceMood, language: str = "en") -> str:
    """Get SSML-style prosody hints for TTS (legacy stub).

    Fish Audio does not use SSML.  Returns empty string for all inputs.

    Args:
        mood: Voice mood.
        language: Language code.

    Returns:
        Empty string (Fish Audio doesn't support SSML hints).
    """
    return ""


# ---------------------------------------------------------------------------
# ProsodyConfig class — kept for backward-compat
# ---------------------------------------------------------------------------


class ProsodyConfig:
    """Manages prosody configuration and state."""

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
