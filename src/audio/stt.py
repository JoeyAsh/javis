"""Speech-to-Text module for JARVIS.

Uses faster-whisper for efficient speech recognition with
automatic language detection.
"""

import asyncio
from dataclasses import dataclass
from typing import Any

import numpy as np

from utils.config_loader import get_config
from utils.logger import get_logger

logger = get_logger("stt")


@dataclass
class TranscriptionResult:
    """Result of speech transcription."""

    text: str
    language: str
    confidence: float


class SpeechToText:
    """Speech-to-text engine using faster-whisper."""

    def __init__(
        self,
        model: str = "large-v3",
        device: str = "cuda",
        compute_type: str = "float16",
        language: str | None = None,
    ) -> None:
        """Initialize the STT engine.

        Args:
            model: Whisper model size (tiny, base, small, medium, large-v3)
            device: Device to use (cuda, cpu)
            compute_type: Compute type (float16, int8, float32)
            language: Force specific language or None for auto-detect
        """
        self.model_name = model
        self.device = device
        self.compute_type = compute_type
        self.forced_language = language
        self._model: Any = None

    async def initialize(self) -> None:
        """Load the Whisper model."""
        loop = asyncio.get_event_loop()

        def load_model() -> Any:
            try:
                from faster_whisper import WhisperModel

                logger.info(
                    f"Loading Whisper model: {self.model_name} "
                    f"(device={self.device}, compute_type={self.compute_type})"
                )

                model = WhisperModel(
                    self.model_name,
                    device=self.device,
                    compute_type=self.compute_type,
                )

                logger.info("Whisper model loaded successfully")
                return model

            except ImportError:
                logger.error(
                    "faster-whisper not installed. Run: pip install faster-whisper"
                )
                raise
            except Exception as e:
                logger.error(f"Failed to load Whisper model: {e}")
                raise

        self._model = await loop.run_in_executor(None, load_model)

    async def transcribe(self, audio_data: bytes | np.ndarray) -> TranscriptionResult:
        """Transcribe audio to text.

        Args:
            audio_data: Audio data as bytes (16-bit PCM) or numpy array

        Returns:
            TranscriptionResult with text, language, and confidence
        """
        if self._model is None:
            await self.initialize()

        loop = asyncio.get_event_loop()

        def process() -> TranscriptionResult:
            # Convert bytes to numpy array if needed
            if isinstance(audio_data, bytes):
                audio_array = np.frombuffer(audio_data, dtype=np.int16)
                audio_array = audio_array.astype(np.float32) / 32768.0
            else:
                audio_array = audio_data.astype(np.float32)
                if audio_array.max() > 1.0:
                    audio_array = audio_array / 32768.0

            # Transcribe
            segments, info = self._model.transcribe(
                audio_array,
                language=self.forced_language,
                beam_size=5,
                vad_filter=True,
                vad_parameters=dict(
                    min_silence_duration_ms=500,
                    speech_pad_ms=200,
                ),
            )

            # Collect all segments
            text_parts = []
            total_confidence = 0.0
            segment_count = 0

            for segment in segments:
                text_parts.append(segment.text.strip())
                total_confidence += segment.avg_logprob
                segment_count += 1

            text = " ".join(text_parts)
            avg_confidence = (
                total_confidence / segment_count if segment_count > 0 else 0.0
            )

            # Convert log probability to 0-1 confidence
            # avg_logprob typically ranges from -1 (good) to -2+ (bad)
            confidence = min(1.0, max(0.0, 1.0 + avg_confidence))

            detected_language = info.language if info.language else "en"

            logger.debug(
                f"Transcribed: '{text[:50]}...' "
                f"(lang={detected_language}, conf={confidence:.2f})"
            )

            return TranscriptionResult(
                text=text,
                language=detected_language,
                confidence=confidence,
            )

        return await loop.run_in_executor(None, process)

    async def transcribe_file(self, file_path: str) -> TranscriptionResult:
        """Transcribe audio from a file.

        Args:
            file_path: Path to audio file (WAV, MP3, etc.)

        Returns:
            TranscriptionResult with text, language, and confidence
        """
        if self._model is None:
            await self.initialize()

        loop = asyncio.get_event_loop()

        def process() -> TranscriptionResult:
            segments, info = self._model.transcribe(
                file_path,
                language=self.forced_language,
                beam_size=5,
                vad_filter=True,
            )

            text_parts = []
            total_confidence = 0.0
            segment_count = 0

            for segment in segments:
                text_parts.append(segment.text.strip())
                total_confidence += segment.avg_logprob
                segment_count += 1

            text = " ".join(text_parts)
            avg_confidence = (
                total_confidence / segment_count if segment_count > 0 else 0.0
            )
            confidence = min(1.0, max(0.0, 1.0 + avg_confidence))
            detected_language = info.language if info.language else "en"

            return TranscriptionResult(
                text=text,
                language=detected_language,
                confidence=confidence,
            )

        return await loop.run_in_executor(None, process)


async def create_stt_engine(config: dict[str, Any] | None = None) -> SpeechToText:
    """Factory function to create STT engine.

    Args:
        config: Optional STT configuration. If None, loads from global config.

    Returns:
        Configured SpeechToText instance
    """
    if config is None:
        cfg = get_config()
        config = cfg.get_section("stt")

    engine = SpeechToText(
        model=config.get("model", "large-v3"),
        device=config.get("device", "cuda"),
        compute_type=config.get("compute_type", "float16"),
        language=config.get("language"),
    )

    await engine.initialize()
    return engine
