"""Wake word detection for JARVIS.

Uses OpenWakeWord for efficient on-device wake word detection.
"""

import asyncio
import base64
import io
from pathlib import Path
from typing import Any

import numpy as np
import sounddevice as sd
import soundfile as sf

from utils.config_loader import get_config
from utils.logger import get_logger

logger = get_logger("wake_word")

# Base64-encoded short chime sound (a simple beep)
# This is a minimal WAV file with a short sine wave tone
CHIME_WAV_BASE64 = (
    "UklGRlQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YTAAAACA/3//f/9//3//f/9//3//"
    "f/9//3//f/9//3//f/9//3//f/9//3//f/9//3//f/9//38A"
)


class WakeWordDetector:
    """Wake word detection using OpenWakeWord."""

    def __init__(
        self,
        model_path: str | None = None,
        threshold: float = 0.5,
        vad_threshold: float = 0.5,
    ) -> None:
        """Initialize the wake word detector.

        Args:
            model_path: Path to custom ONNX model. None uses built-in "hey_jarvis".
            threshold: Detection threshold (0-1)
            vad_threshold: Voice activity detection threshold (0-1)
        """
        self.model_path = model_path
        self.threshold = threshold
        self.vad_threshold = vad_threshold
        self._model: Any = None
        self._chime_audio: np.ndarray | None = None
        self._chime_sample_rate: int = 16000

    async def initialize(self) -> None:
        """Load the wake word model and chime sound."""
        loop = asyncio.get_event_loop()

        def load_model() -> Any:
            try:
                import openwakeword
                from openwakeword.model import Model

                logger.info("Loading OpenWakeWord model...")

                # Download default models if needed
                openwakeword.utils.download_models()

                if self.model_path and Path(self.model_path).exists():
                    model = Model(
                        wakeword_models=[self.model_path],
                        vad_threshold=self.vad_threshold,
                    )
                    logger.info(f"Loaded custom wake word model: {self.model_path}")
                else:
                    # Use built-in "hey jarvis" model
                    model = Model(
                        wakeword_models=["hey_jarvis"],
                        vad_threshold=self.vad_threshold,
                    )
                    logger.info("Loaded built-in 'hey_jarvis' wake word model")

                return model

            except ImportError:
                logger.error(
                    "openwakeword not installed. Run: pip install openWakeWord"
                )
                raise
            except Exception as e:
                logger.error(f"Failed to load wake word model: {e}")
                raise

        self._model = await loop.run_in_executor(None, load_model)
        self._load_chime()

    def _load_chime(self) -> None:
        """Load or generate the activation chime sound."""
        # First, try to load custom chime from voices directory
        chime_path = Path(__file__).parent.parent.parent / "voices" / "chime.wav"

        if chime_path.exists():
            try:
                self._chime_audio, self._chime_sample_rate = sf.read(chime_path)
                self._chime_audio = self._chime_audio.astype(np.float32)
                logger.debug("Loaded custom chime sound")
                return
            except Exception as e:
                logger.warning(f"Failed to load custom chime: {e}")

        # Generate a simple synthesized chime
        self._generate_chime()

    def _generate_chime(self) -> None:
        """Generate a simple activation chime sound."""
        sample_rate = 22050
        duration = 0.15  # seconds

        # Generate a pleasant two-tone chime
        t = np.linspace(0, duration, int(sample_rate * duration), dtype=np.float32)

        # Two frequencies for a pleasant chime
        freq1 = 880  # A5
        freq2 = 1320  # E6

        # Generate tones with envelope
        envelope = np.exp(-t * 8)  # Quick decay

        tone1 = np.sin(2 * np.pi * freq1 * t) * envelope
        tone2 = np.sin(2 * np.pi * freq2 * t) * envelope * 0.7

        # Mix tones
        chime = (tone1 + tone2) * 0.3  # Reduce volume

        self._chime_audio = chime.astype(np.float32)
        self._chime_sample_rate = sample_rate
        logger.debug("Generated synthesized chime")

    async def listen_for_wake_word(
        self, audio_stream: Any, timeout: float | None = None
    ) -> bool:
        """Listen for wake word in audio stream.

        Args:
            audio_stream: Async generator yielding audio chunks
            timeout: Optional timeout in seconds

        Returns:
            True if wake word detected, False if timeout
        """
        if self._model is None:
            await self.initialize()

        start_time = asyncio.get_event_loop().time()

        async for chunk in audio_stream:
            # Check timeout
            if timeout and (asyncio.get_event_loop().time() - start_time) > timeout:
                return False

            # Process audio chunk
            detected = await self._process_chunk(chunk)
            if detected:
                await self.play_chime()
                return True

        return False

    async def _process_chunk(self, audio_chunk: np.ndarray) -> bool:
        """Process a single audio chunk for wake word detection.

        Args:
            audio_chunk: Audio data as numpy array

        Returns:
            True if wake word detected
        """
        loop = asyncio.get_event_loop()

        def predict() -> bool:
            # Ensure correct shape (1D array of int16 samples)
            if audio_chunk.dtype == np.float32:
                # Convert float32 to int16
                chunk_int16 = (audio_chunk * 32767).astype(np.int16)
            else:
                chunk_int16 = audio_chunk.astype(np.int16)

            # Flatten if needed
            if chunk_int16.ndim > 1:
                chunk_int16 = chunk_int16.flatten()

            # Get predictions
            prediction = self._model.predict(chunk_int16)

            # Check if any wake word exceeds threshold
            for model_name, score in prediction.items():
                if score > self.threshold:
                    logger.debug(f"Wake word detected: {model_name} (score={score:.3f})")
                    return True

            return False

        return await loop.run_in_executor(None, predict)

    async def detect_single(self, audio_chunk: np.ndarray) -> dict[str, float]:
        """Run detection on a single audio chunk.

        Args:
            audio_chunk: Audio data as numpy array

        Returns:
            Dictionary of model names to detection scores
        """
        if self._model is None:
            await self.initialize()

        loop = asyncio.get_event_loop()

        def predict() -> dict[str, float]:
            if audio_chunk.dtype == np.float32:
                chunk_int16 = (audio_chunk * 32767).astype(np.int16)
            else:
                chunk_int16 = audio_chunk.astype(np.int16)

            if chunk_int16.ndim > 1:
                chunk_int16 = chunk_int16.flatten()

            return self._model.predict(chunk_int16)

        return await loop.run_in_executor(None, predict)

    async def play_chime(self) -> None:
        """Play the wake word activation chime."""
        if self._chime_audio is None:
            return

        loop = asyncio.get_event_loop()
        event = asyncio.Event()

        def play() -> None:
            sd.play(self._chime_audio, self._chime_sample_rate)
            sd.wait()
            loop.call_soon_threadsafe(event.set)

        await loop.run_in_executor(None, play)
        await event.wait()

    def reset(self) -> None:
        """Reset the wake word model state."""
        if self._model:
            self._model.reset()


async def create_wake_word_detector(
    config: dict[str, Any] | None = None,
) -> WakeWordDetector:
    """Factory function to create wake word detector.

    Args:
        config: Optional configuration. If None, loads from global config.

    Returns:
        Configured WakeWordDetector instance
    """
    if config is None:
        cfg = get_config()
        config = cfg.get_section("wake_word")

    detector = WakeWordDetector(
        model_path=config.get("model_path"),
        threshold=config.get("threshold", 0.5),
        vad_threshold=config.get("vad_threshold", 0.5),
    )

    await detector.initialize()
    return detector
