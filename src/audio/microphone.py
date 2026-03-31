"""Microphone input module for JARVIS.

Provides async audio streaming from the system microphone.
"""

import asyncio
from collections.abc import AsyncGenerator
from typing import Any

import numpy as np
import sounddevice as sd

from src.utils.config_loader import get_config
from src.utils.logger import get_logger

logger = get_logger("microphone")


class DeviceNotFoundError(Exception):
    """Raised when the specified audio device is not found."""

    pass


class Microphone:
    """Async microphone input stream."""

    def __init__(
        self,
        device_index: int | None = None,
        sample_rate: int = 16000,
        chunk_size: int = 1024,
        channels: int = 1,
    ) -> None:
        """Initialize the microphone.

        Args:
            device_index: Audio input device index. None for default.
            sample_rate: Sample rate in Hz
            chunk_size: Number of samples per chunk
            channels: Number of audio channels
        """
        self.device_index = device_index
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.channels = channels
        self._stream: sd.InputStream | None = None
        self._queue: asyncio.Queue[np.ndarray] = asyncio.Queue()
        self._running = False

    def _audio_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info: Any,
        status: sd.CallbackFlags,
    ) -> None:
        """Callback for audio stream.

        Args:
            indata: Input audio data
            frames: Number of frames
            time_info: Time information
            status: Stream status flags
        """
        if status:
            logger.warning(f"Audio input status: {status}")

        # Put audio data into queue (copy to avoid buffer reuse issues)
        try:
            self._queue.put_nowait(indata.copy())
        except asyncio.QueueFull:
            logger.warning("Audio queue full, dropping frame")

    async def start(self) -> None:
        """Start the audio stream."""
        if self._running:
            return

        try:
            # Verify device exists
            devices = sd.query_devices()
            if self.device_index is not None:
                if self.device_index >= len(devices):
                    raise DeviceNotFoundError(
                        f"Audio device index {self.device_index} not found. "
                        f"Available: {len(devices)} devices"
                    )
                device_info = devices[self.device_index]
                logger.info(f"Using audio device: {device_info['name']}")
            else:
                default_input = sd.query_devices(kind="input")
                logger.info(f"Using default audio device: {default_input['name']}")

            # Create input stream
            self._stream = sd.InputStream(
                device=self.device_index,
                channels=self.channels,
                samplerate=self.sample_rate,
                blocksize=self.chunk_size,
                dtype=np.float32,
                callback=self._audio_callback,
            )

            self._stream.start()
            self._running = True
            logger.info("Microphone started")

        except sd.PortAudioError as e:
            logger.error(f"Failed to start microphone: {e}")
            raise DeviceNotFoundError(f"Audio device error: {e}")

    async def stop(self) -> None:
        """Stop the audio stream."""
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        self._running = False
        logger.info("Microphone stopped")

    async def stream_audio(self) -> AsyncGenerator[np.ndarray, None]:
        """Async generator yielding audio chunks.

        Yields:
            Audio data as numpy arrays (float32, mono, sample_rate Hz)
        """
        if not self._running:
            await self.start()

        while self._running:
            try:
                # Wait for audio data with timeout
                chunk = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                yield chunk
            except asyncio.TimeoutError:
                # No audio received, continue waiting
                continue
            except Exception as e:
                logger.error(f"Audio stream error: {e}")
                break

    async def read_chunk(self, timeout: float = 1.0) -> np.ndarray | None:
        """Read a single audio chunk.

        Args:
            timeout: Maximum time to wait for audio

        Returns:
            Audio chunk or None if timeout
        """
        if not self._running:
            await self.start()

        try:
            return await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    @property
    def is_running(self) -> bool:
        """Check if the microphone is currently running."""
        return self._running

    @staticmethod
    def list_devices() -> list[dict[str, Any]]:
        """List available audio input devices.

        Returns:
            List of device information dictionaries
        """
        devices = sd.query_devices()
        input_devices = []

        for i, device in enumerate(devices):
            if device["max_input_channels"] > 0:
                input_devices.append(
                    {
                        "index": i,
                        "name": device["name"],
                        "channels": device["max_input_channels"],
                        "sample_rate": device["default_samplerate"],
                    }
                )

        return input_devices


async def create_microphone(config: dict[str, Any] | None = None) -> Microphone:
    """Factory function to create microphone.

    Args:
        config: Optional audio configuration. If None, loads from global config.

    Returns:
        Configured Microphone instance
    """
    if config is None:
        cfg = get_config()
        config = cfg.get_section("audio")

    mic = Microphone(
        device_index=config.get("input_device_index"),
        sample_rate=config.get("sample_rate", 16000),
        chunk_size=config.get("chunk_size", 1024),
    )

    return mic
