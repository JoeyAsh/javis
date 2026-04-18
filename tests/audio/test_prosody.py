"""Tests for src/audio/prosody.py — get_prosody_hint() and related helpers.

Covers:
- Hour-band → speed/energy mapping for all four time windows.
- enabled=False always returns the neutral hint.
- hour=None uses datetime.now().hour (mocked).
- All returned hint dicts have 'speed' and 'energy' keys.
- Legacy get_voice_mood / get_fish_audio_params still work.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from audio.prosody import (
    ProsodyHint,
    VoiceMood,
    get_fish_audio_params,
    get_prosody_hint,
    get_voice_mood,
)


# ---------------------------------------------------------------------------
# get_prosody_hint — time-of-day bands
# ---------------------------------------------------------------------------


class TestGetProsodyHint:
    """Hour-based prosody hint selection."""

    @pytest.mark.parametrize("hour", [0, 3, 5])
    def test_night_hours_calm_and_slow(self, hour: int) -> None:
        """Hours 0–5 → speed=0.92, energy='calm'."""
        hint = get_prosody_hint(hour=hour)
        assert hint["speed"] == pytest.approx(0.92)
        assert hint["energy"] == "calm"

    @pytest.mark.parametrize("hour", [6, 8, 9])
    def test_morning_hours_bright_and_fast(self, hour: int) -> None:
        """Hours 6–9 → speed=1.05, energy='bright'."""
        hint = get_prosody_hint(hour=hour)
        assert hint["speed"] == pytest.approx(1.05)
        assert hint["energy"] == "bright"

    @pytest.mark.parametrize("hour", [10, 14, 19])
    def test_day_hours_neutral(self, hour: int) -> None:
        """Hours 10–19 → speed=1.0, energy='neutral'."""
        hint = get_prosody_hint(hour=hour)
        assert hint["speed"] == pytest.approx(1.0)
        assert hint["energy"] == "neutral"

    @pytest.mark.parametrize("hour", [20, 22, 23])
    def test_evening_hours_calm(self, hour: int) -> None:
        """Hours 20–23 → speed=0.95, energy='calm'."""
        hint = get_prosody_hint(hour=hour)
        assert hint["speed"] == pytest.approx(0.95)
        assert hint["energy"] == "calm"

    def test_disabled_returns_neutral_hint(self) -> None:
        """enabled=False always returns the neutral no-op hint."""
        for hour in [0, 7, 15, 21]:
            hint = get_prosody_hint(hour=hour, enabled=False)
            assert hint["speed"] == pytest.approx(1.0)
            assert hint["energy"] == "neutral"

    def test_hint_has_required_keys(self) -> None:
        """All returned dicts have 'speed' and 'energy' keys."""
        for hour in range(24):
            hint = get_prosody_hint(hour=hour)
            assert "speed" in hint
            assert "energy" in hint

    def test_none_hour_uses_current_time(self) -> None:
        """When hour=None, datetime.now().hour is used."""
        with patch("audio.prosody.datetime") as mock_dt:
            mock_dt.now.return_value.hour = 8
            hint = get_prosody_hint(hour=None)
        # hour=8 → morning → bright
        assert hint["energy"] == "bright"


# ---------------------------------------------------------------------------
# Legacy helpers — backward-compat
# ---------------------------------------------------------------------------


class TestLegacyHelpers:
    """Existing get_voice_mood / get_fish_audio_params still work."""

    def test_get_voice_mood_morning(self) -> None:
        """Hour 8 → BRIGHT."""
        assert get_voice_mood(hour=8) == VoiceMood.BRIGHT

    def test_get_voice_mood_night(self) -> None:
        """Hour 2 → CALM."""
        assert get_voice_mood(hour=2) == VoiceMood.CALM

    def test_get_voice_mood_day(self) -> None:
        """Hour 14 → NEUTRAL."""
        assert get_voice_mood(hour=14) == VoiceMood.NEUTRAL

    def test_get_fish_audio_params_has_speed(self) -> None:
        """All VoiceMood values produce a dict with a 'speed' key."""
        for mood in VoiceMood:
            params = get_fish_audio_params(mood)
            assert "speed" in params
