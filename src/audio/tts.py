"""Text-to-Speech engine for JARVIS.

Supports XTTS-v2 for high-quality voice cloning on PC,
and Piper TTS for efficient CPU-only synthesis on Raspberry Pi.
"""

import asyncio
import io
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import numpy as np
import sounddevice as sd
import soundfile as sf
from scipy import signal

from utils.config_loader import get_config
from utils.logger import get_logger

logger = get_logger("tts")


class TTSEngine(ABC):
    """Abstract base class for text-to-speech engines."""

    def __init__(self) -> None:
        """Initialize the TTS engine."""
        self._speaking = False
        self._queue: asyncio.Queue[tuple[str, str | None]] = asyncio.Queue()
        self._stop_event = asyncio.Event()
        self._current_stream: sd.OutputStream | None = None

    @abstractmethod
    async def _synthesize(self, text: str, language: str | None = None) -> tuple[np.ndarray, int]:
        """Synthesize text to audio data.

        Args:
            text: Text to synthesize
            language: Language code (e.g. 'de', 'en'). None for auto-detect.

        Returns:
            Tuple of (audio_data as numpy array, sample_rate)
        """
        pass

    async def speak(self, text: str, language: str | None = None) -> None:
        """Speak the given text and wait until finished.

        Args:
            text: Text to speak
            language: Language code (e.g. 'de', 'en'). None for auto-detect.
        """
        await self._queue.put((text, language))

        if not self._speaking:
            self._speaking = True
            await self._process_queue()

    async def _process_queue(self) -> None:
        """Process the speech queue."""
        try:
            while not self._queue.empty():
                if self._stop_event.is_set():
                    # Clear the queue
                    while not self._queue.empty():
                        try:
                            self._queue.get_nowait()
                        except asyncio.QueueEmpty:
                            break
                    self._stop_event.clear()
                    break

                text, language = await self._queue.get()
                logger.debug(f"Synthesizing (lang={language}): {text[:50]}...")

                try:
                    audio_data, sample_rate = await self._synthesize(text, language)
                    await self._play_audio(audio_data, sample_rate)
                except Exception as e:
                    logger.error(f"TTS synthesis error: {e}")
        finally:
            self._speaking = False

    async def _play_audio(self, audio_data: np.ndarray, sample_rate: int) -> None:
        """Play audio data through the default output device.

        Args:
            audio_data: Audio samples as numpy array
            sample_rate: Sample rate in Hz
        """
        loop = asyncio.get_running_loop()
        event = asyncio.Event()

        def callback(
            outdata: np.ndarray,
            frames: int,
            time_info: Any,
            status: sd.CallbackFlags,
        ) -> None:
            if status:
                logger.warning(f"Audio playback status: {status}")

        try:
            # Ensure audio is in the correct format
            if audio_data.ndim == 1:
                audio_data = audio_data.reshape(-1, 1)

            # Normalize audio
            max_val = np.abs(audio_data).max()
            if max_val > 0:
                audio_data = audio_data / max_val * 0.9

            # Play using sounddevice
            def play_sync() -> None:
                sd.play(audio_data, sample_rate)
                sd.wait()
                loop.call_soon_threadsafe(event.set)

            await loop.run_in_executor(None, play_sync)
            await event.wait()

        except Exception as e:
            logger.error(f"Audio playback error: {e}")

    async def stop_speaking(self) -> None:
        """Interrupt current speech and clear the queue."""
        self._stop_event.set()
        sd.stop()
        logger.debug("Speech interrupted")

    @property
    def is_speaking(self) -> bool:
        """Check if currently speaking."""
        return self._speaking


class XTTSEngine(TTSEngine):
    """Coqui XTTS-v2 text-to-speech engine for voice cloning."""

    def __init__(
        self,
        voice_profile: str = "jarvis",
        speed: float = 1.0,
        pitch_shift: int = 0,
    ) -> None:
        """Initialize XTTS engine.

        Args:
            voice_profile: Name of voice profile (without .wav extension)
            speed: Speech speed multiplier
            pitch_shift: Pitch shift in semitones
        """
        super().__init__()
        self.voice_profile = voice_profile
        self.speed = speed
        self.pitch_shift = pitch_shift
        self._model: Any = None
        self._voice_path: Path | None = None

    async def initialize(self) -> None:
        """Load the XTTS model and voice profile."""
        loop = asyncio.get_event_loop()

        def load_model() -> Any:
            try:
                from TTS.api import TTS

                logger.info("Loading XTTS-v2 model...")
                model = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
                logger.info("XTTS-v2 model loaded")
                return model
            except ImportError:
                logger.error("TTS package not installed. Run: pip install TTS")
                raise
            except Exception as e:
                logger.error(f"Failed to load XTTS model: {e}")
                raise

        self._model = await loop.run_in_executor(None, load_model)
        self._load_voice_profile()

    def _load_voice_profile(self) -> None:
        """Load the voice profile WAV file."""
        voices_dir = Path(__file__).parent.parent.parent / "voices"
        voice_file = voices_dir / f"{self.voice_profile}.wav"

        if voice_file.exists():
            self._voice_path = voice_file
            logger.info(f"Loaded voice profile: {self.voice_profile}")
        else:
            logger.warning(
                f"Voice profile '{self.voice_profile}' not found at {voice_file}"
            )
            # Try to find any available voice
            wav_files = list(voices_dir.glob("*.wav"))
            if wav_files:
                self._voice_path = wav_files[0]
                logger.info(f"Using fallback voice: {self._voice_path.stem}")
            else:
                logger.warning("No voice profiles found in voices/")
                self._voice_path = None

    def _apply_pitch_shift(
        self, audio: np.ndarray, sample_rate: int, semitones: int
    ) -> np.ndarray:
        """Apply pitch shift to audio using scipy.

        Args:
            audio: Audio data as numpy array
            sample_rate: Sample rate in Hz
            semitones: Number of semitones to shift

        Returns:
            Pitch-shifted audio data
        """
        if semitones == 0:
            return audio

        # Calculate the pitch shift ratio
        ratio = 2 ** (semitones / 12.0)

        # Resample to shift pitch
        n_samples = int(len(audio) / ratio)
        shifted = signal.resample(audio, n_samples)

        # Resample back to original length to maintain duration
        result = signal.resample(shifted, len(audio))

        return result.astype(np.float32)

    async def _synthesize(self, text: str, language: str | None = None) -> tuple[np.ndarray, int]:
        """Synthesize text using XTTS-v2.

        Args:
            text: Text to synthesize
            language: Language code (e.g. 'de', 'en')

        Returns:
            Tuple of (audio_data, sample_rate)
        """
        if self._model is None:
            await self.initialize()

        loop = asyncio.get_event_loop()

        def generate() -> tuple[np.ndarray, int]:
            # Use provided language or detect from text
            lang = language
            if not lang:
                german_chars = set("äöüßÄÖÜ")
                lang = "de" if any(c in text for c in german_chars) else "en"

            if self._voice_path:
                wav = self._model.tts(
                    text=text,
                    speaker_wav=str(self._voice_path),
                    language=lang,
                    speed=self.speed,
                )
            else:
                # Use default speaker if no voice profile
                wav = self._model.tts(text=text, language=lang, speed=self.speed)

            audio_data = np.array(wav, dtype=np.float32)
            return audio_data, 24000  # XTTS uses 24kHz

        audio_data, sample_rate = await loop.run_in_executor(None, generate)

        # Apply pitch shift if configured
        if self.pitch_shift != 0:
            audio_data = self._apply_pitch_shift(audio_data, sample_rate, self.pitch_shift)

        return audio_data, sample_rate

    def set_voice_profile(self, profile: str) -> None:
        """Change the voice profile.

        Args:
            profile: Name of voice profile (without .wav extension)
        """
        self.voice_profile = profile
        self._load_voice_profile()


class PiperEngine(TTSEngine):
    """Piper TTS engine with automatic language detection."""

    # Language-to-model mapping
    LANGUAGE_MODELS: dict[str, str] = {
        "de": "de_DE-thorsten-high",
        "en": "en_GB-alan-medium",
    }
    DEFAULT_LANGUAGE = "de"

    def __init__(
        self,
        model_name: str = "de_DE-thorsten-high",
        speed: float = 1.0,
    ) -> None:
        """Initialize Piper engine.

        Args:
            model_name: Default Piper model name
            speed: Speech speed multiplier
        """
        super().__init__()
        self.model_name = model_name
        self.speed = speed
        self._voices: dict[str, Any] = {}
        self._data_dir = Path.home() / ".local" / "share" / "piper-voices"

    def _load_voice(self, model_name: str) -> Any:
        """Load a single Piper voice model.

        Args:
            model_name: Model name to load

        Returns:
            PiperVoice instance or None
        """
        from piper import PiperVoice

        model_path = self._data_dir / f"{model_name}.onnx"
        config_path = self._data_dir / f"{model_name}.onnx.json"

        if model_path.exists():
            voice = PiperVoice.load(str(model_path), str(config_path))
            logger.info(f"Piper model loaded: {model_name}")
            return voice
        else:
            logger.warning(f"Piper model not found: {model_path}")
            return None

    async def initialize(self) -> None:
        """Load all available Piper voice models."""
        loop = asyncio.get_event_loop()

        def load_models() -> dict[str, Any]:
            try:
                voices: dict[str, Any] = {}
                self._data_dir.mkdir(parents=True, exist_ok=True)

                # Load language-specific models
                for lang, model in self.LANGUAGE_MODELS.items():
                    voice = self._load_voice(model)
                    if voice:
                        voices[lang] = voice

                # Load default model as fallback
                if not voices:
                    voice = self._load_voice(self.model_name)
                    if voice:
                        voices["default"] = voice

                if not voices:
                    logger.error("No Piper voices available")

                return voices

            except ImportError:
                logger.error("piper-tts not installed. Run: pip install piper-tts")
                raise
            except Exception as e:
                logger.error(f"Failed to load Piper models: {e}")
                raise

        self._voices = await loop.run_in_executor(None, load_models)

    def _detect_language(self, text: str) -> str:
        """Detect language of text using simple heuristics.

        Args:
            text: Text to analyze

        Returns:
            Language code ('de' or 'en')
        """
        german_indicators = set("äöüßÄÖÜ")
        german_words = {
            "ich", "du", "er", "sie", "wir", "ihr", "das", "ist", "und",
            "der", "die", "den", "dem", "ein", "eine", "nicht", "habe",
            "bitte", "danke", "wie", "was", "wer", "wo", "warum", "kann",
            "sind", "haben", "werden", "guten", "morgen", "abend", "tag",
            "ja", "nein", "auch", "aber", "oder", "wenn", "dass", "mit",
            "auf", "für", "von", "zu", "aus", "bei", "nach", "über",
        }

        # Check for German-specific characters
        if any(c in text for c in german_indicators):
            return "de"

        # Check for German words
        words = set(text.lower().split())
        german_count = len(words & german_words)
        if german_count >= 2 or (german_count >= 1 and len(words) <= 4):
            return "de"

        return "en"

    async def _synthesize(self, text: str, language: str | None = None) -> tuple[np.ndarray, int]:
        """Synthesize text using Piper with language selection.

        Args:
            text: Text to synthesize
            language: Language code from STT. Falls back to text-based detection.

        Returns:
            Tuple of (audio_data, sample_rate)
        """
        if not self._voices:
            await self.initialize()

        if not self._voices:
            logger.error("No Piper voices available")
            return np.zeros(16000, dtype=np.float32), 16000

        # Use explicit language if provided, otherwise auto-detect from text
        lang = language if language and language in self._voices else self._detect_language(text)
        voice = self._voices.get(lang) or next(iter(self._voices.values()))
        logger.info(f"TTS: language={lang}, text={text[:60]}...")

        loop = asyncio.get_event_loop()

        def generate() -> tuple[np.ndarray, int]:
            import os
            import tempfile
            import wave

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = tmp.name

            try:
                with wave.open(tmp_path, "wb") as wav_file:
                    voice.synthesize_wav(text, wav_file)

                with wave.open(tmp_path, "rb") as wav_file:
                    sample_rate = wav_file.getframerate()
                    frames = wav_file.readframes(wav_file.getnframes())

                audio_data = np.frombuffer(frames, dtype=np.int16)
                audio_data = audio_data.astype(np.float32) / 32768.0
            finally:
                os.unlink(tmp_path)

            return audio_data, sample_rate

        return await loop.run_in_executor(None, generate)


class MockTTSEngine(TTSEngine):
    """Mock TTS engine for testing without audio output."""

    async def _synthesize(self, text: str, language: str | None = None) -> tuple[np.ndarray, int]:
        """Return silence for testing.

        Args:
            text: Text to synthesize (logged only)
            language: Ignored in mock engine

        Returns:
            Tuple of (silence, sample_rate)
        """
        logger.debug(f"MockTTS would speak: {text}")
        # Return 0.1 seconds of silence
        return np.zeros(1600, dtype=np.float32), 16000


async def create_tts_engine(config: dict[str, Any] | None = None) -> TTSEngine:
    """Factory function to create the appropriate TTS engine.

    Args:
        config: Optional TTS configuration. If None, loads from global config.

    Returns:
        Configured TTSEngine instance
    """
    if config is None:
        cfg = get_config()
        config = cfg.get_section("tts")

    engine_type = config.get("engine", "xtts")
    voice_profile = config.get("voice_profile", "jarvis")
    speed = config.get("speed", 1.0)
    pitch_shift = config.get("pitch_shift", 0)

    if engine_type == "xtts":
        engine = XTTSEngine(
            voice_profile=voice_profile,
            speed=speed,
            pitch_shift=pitch_shift,
        )
    elif engine_type == "piper":
        piper_model = config.get("piper_model", "en_US-lessac-medium")
        engine = PiperEngine(model_name=piper_model, speed=speed)
    elif engine_type == "mock":
        engine = MockTTSEngine()
    else:
        logger.warning(f"Unknown TTS engine: {engine_type}, using mock")
        engine = MockTTSEngine()

    await engine.initialize() if hasattr(engine, "initialize") else None
    return engine
