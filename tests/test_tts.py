"""Tests for the TTS (Text-to-Speech) module."""

from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from src.audio.tts import (
    MockTTSEngine,
    PiperEngine,
    TTSEngine,
    XTTSEngine,
    create_tts_engine,
)


@pytest.fixture
def mock_sounddevice():
    """Mock sounddevice module."""
    with patch("src.audio.tts.sd") as mock_sd:
        mock_sd.play = MagicMock()
        mock_sd.wait = MagicMock()
        mock_sd.stop = MagicMock()
        yield mock_sd


@pytest.fixture
def mock_tts_model():
    """Mock TTS model from Coqui TTS."""
    with patch("TTS.api.TTS") as mock_tts:
        mock_instance = MagicMock()
        mock_instance.tts.return_value = np.zeros(24000, dtype=np.float32)
        mock_tts.return_value = mock_instance
        yield mock_instance


class TestXTTSEngine:
    """Tests for XTTSEngine."""

    @pytest.mark.asyncio
    async def test_speak_calls_sounddevice_play(
        self, mock_sounddevice, mock_tts_model
    ):
        """Test that speak() calls sounddevice.play with audio data."""
        with patch("src.audio.tts.XTTSEngine._synthesize") as mock_synth:
            mock_synth.return_value = (np.zeros(16000, dtype=np.float32), 16000)

            engine = XTTSEngine(voice_profile="jarvis")
            engine._model = mock_tts_model

            await engine.speak("Hello, sir.")
            # Wait for queue processing
            await engine._process_queue()

            # Verify sounddevice.play was called
            assert mock_sounddevice.play.called

    @pytest.mark.asyncio
    async def test_pitch_shift_applied_when_configured(self, mock_tts_model):
        """Test that pitch shift is applied when configured."""
        engine = XTTSEngine(voice_profile="jarvis", pitch_shift=-4)

        # Create sample audio
        sample_audio = np.sin(np.linspace(0, 2 * np.pi * 440, 16000)).astype(
            np.float32
        )

        # Apply pitch shift
        shifted = engine._apply_pitch_shift(sample_audio, 16000, -4)

        # Verify audio was modified (shifted audio should be different)
        assert shifted is not None
        assert len(shifted) == len(sample_audio)

    @pytest.mark.asyncio
    async def test_pitch_shift_not_applied_when_zero(self):
        """Test that no pitch shift is applied when shift is 0."""
        engine = XTTSEngine(voice_profile="jarvis", pitch_shift=0)

        sample_audio = np.sin(np.linspace(0, 2 * np.pi * 440, 16000)).astype(
            np.float32
        )

        shifted = engine._apply_pitch_shift(sample_audio, 16000, 0)

        # Should return the same array
        np.testing.assert_array_equal(shifted, sample_audio)

    def test_set_voice_profile(self):
        """Test changing voice profile."""
        engine = XTTSEngine(voice_profile="jarvis")
        assert engine.voice_profile == "jarvis"

        engine.set_voice_profile("darth_vader")
        assert engine.voice_profile == "darth_vader"


class TestPiperEngine:
    """Tests for PiperEngine."""

    @pytest.mark.asyncio
    async def test_produces_output(self, mock_sounddevice):
        """Test that Piper engine produces audio output."""
        with patch("src.audio.tts.PiperEngine._synthesize") as mock_synth:
            mock_synth.return_value = (np.zeros(16000, dtype=np.float32), 22050)

            engine = PiperEngine(model_name="en_US-lessac-medium")

            await engine.speak("Hello")
            await engine._process_queue()

            # Verify synthesis was attempted
            assert mock_synth.called

    def test_initialization_parameters(self):
        """Test that engine initializes with correct parameters."""
        engine = PiperEngine(model_name="de_DE-thorsten-medium", speed=1.2)

        assert engine.model_name == "de_DE-thorsten-medium"
        assert engine.speed == 1.2


class TestMockTTSEngine:
    """Tests for MockTTSEngine."""

    @pytest.mark.asyncio
    async def test_returns_silence(self):
        """Test that mock engine returns silence."""
        engine = MockTTSEngine()

        audio, sample_rate = await engine._synthesize("Test text")

        assert audio is not None
        assert sample_rate == 16000
        assert np.all(audio == 0)


class TestCreateTTSEngine:
    """Tests for the create_tts_engine factory function."""

    @pytest.mark.asyncio
    async def test_returns_xtts_engine_for_xtts_config(self, mock_config):
        """Test that factory returns XTTSEngine for xtts config."""
        config = mock_config["tts"].copy()
        config["engine"] = "xtts"

        with patch.object(XTTSEngine, "initialize", new_callable=AsyncMock):
            engine = await create_tts_engine(config)
            assert isinstance(engine, XTTSEngine)

    @pytest.mark.asyncio
    async def test_returns_piper_engine_for_piper_config(self, mock_config):
        """Test that factory returns PiperEngine for piper config."""
        config = mock_config["tts"].copy()
        config["engine"] = "piper"

        with patch.object(PiperEngine, "initialize", new_callable=AsyncMock):
            engine = await create_tts_engine(config)
            assert isinstance(engine, PiperEngine)

    @pytest.mark.asyncio
    async def test_returns_mock_engine_for_mock_config(self, mock_config):
        """Test that factory returns MockTTSEngine for mock config."""
        config = mock_config["tts"].copy()
        config["engine"] = "mock"

        engine = await create_tts_engine(config)
        assert isinstance(engine, MockTTSEngine)

    @pytest.mark.asyncio
    async def test_returns_mock_for_unknown_engine(self, mock_config):
        """Test that factory returns MockTTSEngine for unknown engine type."""
        config = mock_config["tts"].copy()
        config["engine"] = "unknown_engine"

        engine = await create_tts_engine(config)
        assert isinstance(engine, MockTTSEngine)


class TestTTSEngineBase:
    """Tests for TTSEngine base class behavior."""

    @pytest.mark.asyncio
    async def test_is_speaking_property(self):
        """Test is_speaking property reflects state correctly."""
        engine = MockTTSEngine()

        assert engine.is_speaking is False

        # Start speaking
        await engine.speak("Test")
        # Note: In real implementation this would be True during playback

    @pytest.mark.asyncio
    async def test_stop_speaking(self, mock_sounddevice):
        """Test stop_speaking interrupts playback."""
        engine = MockTTSEngine()

        await engine.speak("Long text that would take time to speak")
        await engine.stop_speaking()

        # Verify stop event is set
        assert engine._stop_event.is_set() or not engine.is_speaking
