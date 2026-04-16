"""Unit tests for voice realism UX modules.

Tests cover:
- FillerPlayer
- BackchannelPlayer
- Prosody configuration
- DisfluencyInjector
- TurnDetector
"""

import asyncio
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from audio.backchannels import BackchannelPlayer
from audio.disfluencies import DisfluencyInjector
from audio.fillers import FillerPlayer
from audio.prosody import ProsodyConfig, VoiceMood, get_fish_audio_params, get_voice_mood
from audio.turn_detection import SpeechQueue, TurnDetectionConfig, TurnDetector


class TestFillerPlayer:
    """Tests for FillerPlayer."""

    @pytest.fixture
    def mock_player(self):
        """Provide mock audio player."""
        return AsyncMock()

    @pytest.fixture
    def temp_cache_dir(self):
        """Provide temporary cache directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.mark.asyncio
    async def test_filler_not_played_when_response_arrives(
        self, mock_player, temp_cache_dir
    ):
        """Test that filler is not played if response arrives in time."""
        filler = FillerPlayer(mock_player, temp_cache_dir, delay_threshold_ms=500)

        response_event = asyncio.Event()

        # Set event immediately
        async def set_event():
            await asyncio.sleep(0.1)
            response_event.set()

        asyncio.create_task(set_event())
        await filler.wait_for_response_or_filler(response_event, "en")

        assert filler.filler_played is False

    def test_get_filler_phrases(self, mock_player, temp_cache_dir):
        """Test getting filler phrases."""
        filler = FillerPlayer(mock_player, temp_cache_dir)

        en_phrases = filler.get_filler_phrases("en")
        de_phrases = filler.get_filler_phrases("de")

        assert "One moment" in en_phrases
        assert "Moment" in de_phrases


class TestBackchannelPlayer:
    """Tests for BackchannelPlayer."""

    @pytest.fixture
    def mock_player(self):
        """Provide mock audio player."""
        return AsyncMock()

    @pytest.fixture
    def temp_cache_dir(self):
        """Provide temporary cache directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.mark.asyncio
    async def test_backchannel_not_played_short_silence(
        self, mock_player, temp_cache_dir
    ):
        """Test that backchannel is not played for short silence."""
        player = BackchannelPlayer(
            mock_player,
            temp_cache_dir,
            silence_threshold_ms=1200,
        )

        result = await player.maybe_play(0.5, "en")  # 0.5s < 1.2s threshold

        assert result is False
        mock_player.play.assert_not_called()

    @pytest.mark.asyncio
    async def test_backchannel_respects_interval(
        self, mock_player, temp_cache_dir
    ):
        """Test that backchannel respects minimum interval."""
        player = BackchannelPlayer(
            mock_player,
            temp_cache_dir,
            silence_threshold_ms=500,
            min_interval_seconds=5,
        )

        # Simulate recent backchannel
        player._last_backchannel = time.time()

        result = await player.maybe_play(1.0, "en")

        assert result is False

    def test_reset_timer(self, mock_player, temp_cache_dir):
        """Test resetting the interval timer."""
        player = BackchannelPlayer(mock_player, temp_cache_dir)
        player._last_backchannel = time.time()

        player.reset_timer()

        assert player.last_play_time == 0.0


class TestProsody:
    """Tests for prosody configuration."""

    def test_get_voice_mood_morning(self):
        """Test morning returns BRIGHT mood."""
        mood = get_voice_mood(hour=8)

        assert mood == VoiceMood.BRIGHT

    def test_get_voice_mood_night(self):
        """Test night returns CALM mood."""
        mood = get_voice_mood(hour=23)

        assert mood == VoiceMood.CALM

    def test_get_voice_mood_daytime(self):
        """Test daytime returns NEUTRAL mood."""
        mood = get_voice_mood(hour=14)

        assert mood == VoiceMood.NEUTRAL

    def test_get_voice_mood_error_context(self):
        """Test error context returns SERIOUS mood."""
        mood = get_voice_mood(hour=14, error_context=True)

        assert mood == VoiceMood.SERIOUS

    def test_get_fish_audio_params_all_moods(self):
        """Test that all moods have parameters."""
        for mood in VoiceMood:
            params = get_fish_audio_params(mood)

            assert "speed" in params
            assert "pitch" in params
            assert "volume" in params

    def test_prosody_config_error_context(self):
        """Test ProsodyConfig error context."""
        config = ProsodyConfig()

        config.set_error_context(True)

        assert config.current_mood == VoiceMood.SERIOUS

    def test_prosody_config_override(self):
        """Test ProsodyConfig mood override."""
        config = ProsodyConfig()

        config.set_mood_override(VoiceMood.CALM)

        assert config.current_mood == VoiceMood.CALM

    def test_prosody_config_reset(self):
        """Test ProsodyConfig reset."""
        config = ProsodyConfig()
        config.set_error_context(True)
        config.set_mood_override(VoiceMood.CALM)

        config.reset()

        assert config._error_context is False
        assert config._override_mood is None


class TestDisfluencyInjector:
    """Tests for DisfluencyInjector."""

    def test_disabled_by_default(self):
        """Test disfluencies disabled by default."""
        injector = DisfluencyInjector({})

        assert injector.enabled is False

    def test_no_injection_when_disabled(self):
        """Test no injection when disabled."""
        injector = DisfluencyInjector({"natural_disfluencies": False})

        result = injector.maybe_inject("Hello, Sir.", "en")

        assert result == "Hello, Sir."

    def test_injection_rate(self):
        """Test that injection respects rate."""
        injector = DisfluencyInjector({
            "natural_disfluencies": True,
            "disfluency_rate": 0.0,  # Never inject
        })

        result = injector.maybe_inject("Hello, Sir.", "en")

        assert result == "Hello, Sir."

    def test_set_enabled(self):
        """Test setting enabled state."""
        injector = DisfluencyInjector({})
        assert injector.enabled is False

        injector.set_enabled(True)

        assert injector.enabled is True

    def test_get_phrases(self):
        """Test getting phrases."""
        injector = DisfluencyInjector({})

        en_phrases = injector.get_phrases("en")
        de_phrases = injector.get_phrases("de")

        assert "well" in en_phrases
        assert "also" in de_phrases


class TestTurnDetection:
    """Tests for TurnDetector and related classes."""

    def test_config_defaults(self):
        """Test TurnDetectionConfig defaults."""
        config = TurnDetectionConfig()

        assert config.silence_threshold_ms == 800
        assert config.use_prosodic_hints is False

    @pytest.mark.asyncio
    async def test_turn_complete_silence_threshold(self):
        """Test turn complete on silence threshold."""
        detector = TurnDetector(TurnDetectionConfig(silence_threshold_ms=500))

        result = await detector.is_turn_complete(silence_duration_ms=600)

        assert result is True

    @pytest.mark.asyncio
    async def test_turn_complete_stt_final(self):
        """Test turn complete with STT final flag."""
        detector = TurnDetector(TurnDetectionConfig())

        result = await detector.is_turn_complete(
            silence_duration_ms=400,
            stt_is_final=True,
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_turn_not_complete_short_silence(self):
        """Test turn not complete with short silence."""
        detector = TurnDetector(TurnDetectionConfig(silence_threshold_ms=800))

        result = await detector.is_turn_complete(silence_duration_ms=300)

        assert result is False

    def test_update_config(self):
        """Test updating configuration."""
        detector = TurnDetector(TurnDetectionConfig())

        detector.update_config(silence_threshold_ms=1000)

        assert detector.config.silence_threshold_ms == 1000


class TestSpeechQueue:
    """Tests for SpeechQueue."""

    @pytest.mark.asyncio
    async def test_add_and_pop(self):
        """Test adding and popping utterances."""
        queue = SpeechQueue()

        await queue.add("First utterance")
        await queue.add("Second utterance")

        first = await queue.pop()
        second = await queue.pop()

        assert first == "First utterance"
        assert second == "Second utterance"

    @pytest.mark.asyncio
    async def test_pop_empty_returns_none(self):
        """Test popping from empty queue."""
        queue = SpeechQueue()

        result = await queue.pop()

        assert result is None

    @pytest.mark.asyncio
    async def test_has_pending(self):
        """Test has_pending method."""
        queue = SpeechQueue()

        assert await queue.has_pending() is False

        await queue.add("Utterance")

        assert await queue.has_pending() is True

    @pytest.mark.asyncio
    async def test_clear(self):
        """Test clearing the queue."""
        queue = SpeechQueue()
        await queue.add("Utterance 1")
        await queue.add("Utterance 2")

        await queue.clear()

        assert queue.pending_count == 0

    @pytest.mark.asyncio
    async def test_max_queue_size(self):
        """Test max queue size enforcement."""
        queue = SpeechQueue(max_queue=2)

        await queue.add("First")
        await queue.add("Second")
        await queue.add("Third")  # Should evict "First"

        first = await queue.pop()
        assert first == "Second"  # "First" was evicted
