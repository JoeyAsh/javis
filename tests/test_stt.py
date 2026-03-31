"""Tests for the STT (Speech-to-Text) module."""

from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from src.audio.stt import SpeechToText, TranscriptionResult, create_stt_engine


@pytest.fixture
def mock_whisper_model():
    """Mock faster-whisper WhisperModel."""

    class MockSegment:
        def __init__(self, text, avg_logprob):
            self.text = text
            self.avg_logprob = avg_logprob

    class MockInfo:
        def __init__(self, language):
            self.language = language

    with patch("faster_whisper.WhisperModel") as mock_model_class:
        mock_instance = MagicMock()

        # Default transcribe return value
        mock_instance.transcribe.return_value = (
            [MockSegment("Hello, this is a test.", -0.3)],
            MockInfo("en"),
        )

        mock_model_class.return_value = mock_instance
        yield mock_instance


class TestSpeechToText:
    """Tests for SpeechToText class."""

    @pytest.mark.asyncio
    async def test_transcribe_returns_transcription_result(
        self, mock_whisper_model, sample_audio_bytes
    ):
        """Test that transcribe() returns TranscriptionResult."""
        stt = SpeechToText(model="small", device="cpu")
        stt._model = mock_whisper_model

        result = await stt.transcribe(sample_audio_bytes)

        assert isinstance(result, TranscriptionResult)
        assert hasattr(result, "text")
        assert hasattr(result, "language")
        assert hasattr(result, "confidence")

    @pytest.mark.asyncio
    async def test_transcribe_with_bytes_input(
        self, mock_whisper_model, sample_audio_bytes
    ):
        """Test transcription with bytes input."""
        stt = SpeechToText(model="small", device="cpu")
        stt._model = mock_whisper_model

        result = await stt.transcribe(sample_audio_bytes)

        assert result.text == "Hello, this is a test."
        assert result.language == "en"
        assert 0 <= result.confidence <= 1

    @pytest.mark.asyncio
    async def test_transcribe_with_numpy_input(
        self, mock_whisper_model, sample_audio_numpy
    ):
        """Test transcription with numpy array input."""
        stt = SpeechToText(model="small", device="cpu")
        stt._model = mock_whisper_model

        result = await stt.transcribe(sample_audio_numpy)

        assert isinstance(result, TranscriptionResult)
        assert result.text is not None

    @pytest.mark.asyncio
    async def test_transcribe_detects_german(self, mock_whisper_model, sample_audio_bytes):
        """Test that German language is detected correctly."""

        class MockSegment:
            text = "Hallo, das ist ein Test."
            avg_logprob = -0.4

        class MockInfo:
            language = "de"

        mock_whisper_model.transcribe.return_value = (
            [MockSegment()],
            MockInfo(),
        )

        stt = SpeechToText(model="small", device="cpu")
        stt._model = mock_whisper_model

        result = await stt.transcribe(sample_audio_bytes)

        assert result.language == "de"

    @pytest.mark.asyncio
    async def test_silence_detection_empty_result(self, mock_whisper_model):
        """Test that silence returns empty text."""

        class MockInfo:
            language = "en"

        mock_whisper_model.transcribe.return_value = ([], MockInfo())

        stt = SpeechToText(model="small", device="cpu")
        stt._model = mock_whisper_model

        # Create silent audio
        silent_audio = np.zeros(16000, dtype=np.float32)

        result = await stt.transcribe(silent_audio)

        assert result.text == ""
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_confidence_calculation(self, mock_whisper_model, sample_audio_bytes):
        """Test that confidence is calculated from log probability."""

        class MockSegment:
            text = "Test"
            avg_logprob = -0.5  # Moderate confidence

        class MockInfo:
            language = "en"

        mock_whisper_model.transcribe.return_value = (
            [MockSegment()],
            MockInfo(),
        )

        stt = SpeechToText(model="small", device="cpu")
        stt._model = mock_whisper_model

        result = await stt.transcribe(sample_audio_bytes)

        # Confidence should be between 0 and 1
        assert 0 <= result.confidence <= 1
        # With avg_logprob of -0.5, confidence should be 0.5
        assert result.confidence == pytest.approx(0.5, abs=0.01)

    @pytest.mark.asyncio
    async def test_multiple_segments_concatenated(
        self, mock_whisper_model, sample_audio_bytes
    ):
        """Test that multiple segments are concatenated."""

        class MockSegment1:
            text = "Hello"
            avg_logprob = -0.3

        class MockSegment2:
            text = "world"
            avg_logprob = -0.4

        class MockInfo:
            language = "en"

        mock_whisper_model.transcribe.return_value = (
            [MockSegment1(), MockSegment2()],
            MockInfo(),
        )

        stt = SpeechToText(model="small", device="cpu")
        stt._model = mock_whisper_model

        result = await stt.transcribe(sample_audio_bytes)

        assert "Hello" in result.text
        assert "world" in result.text


class TestCreateSTTEngine:
    """Tests for the create_stt_engine factory function."""

    @pytest.mark.asyncio
    async def test_creates_engine_with_config(self, mock_config, mock_whisper_model):
        """Test that factory creates engine with correct config."""
        config = mock_config["stt"].copy()

        with patch("src.audio.stt.SpeechToText.initialize", new_callable=AsyncMock):
            engine = await create_stt_engine(config)

            assert isinstance(engine, SpeechToText)
            assert engine.model_name == "small"
            assert engine.device == "cpu"
            assert engine.compute_type == "int8"

    @pytest.mark.asyncio
    async def test_forced_language(self, mock_config, mock_whisper_model):
        """Test that forced language is passed to engine."""
        config = mock_config["stt"].copy()
        config["language"] = "de"

        with patch("src.audio.stt.SpeechToText.initialize", new_callable=AsyncMock):
            engine = await create_stt_engine(config)

            assert engine.forced_language == "de"


class TestTranscriptionResult:
    """Tests for TranscriptionResult dataclass."""

    def test_dataclass_fields(self):
        """Test TranscriptionResult has expected fields."""
        result = TranscriptionResult(
            text="Hello",
            language="en",
            confidence=0.9,
        )

        assert result.text == "Hello"
        assert result.language == "en"
        assert result.confidence == 0.9
