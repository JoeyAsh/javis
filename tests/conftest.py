"""Shared pytest fixtures for JARVIS tests."""

import numpy as np
import pytest


@pytest.fixture
def mock_config():
    """Return a mock configuration object for testing."""
    return {
        "jarvis": {
            "name": "JARVIS",
            "wake_word": "hey jarvis",
            "language": "auto",
        },
        "audio": {
            "input_device_index": None,
            "sample_rate": 16000,
            "chunk_size": 1024,
            "silence_threshold": 500,
            "silence_duration_ms": 1500,
        },
        "stt": {
            "model": "small",
            "device": "cpu",
            "compute_type": "int8",
            "language": None,
        },
        "tts": {
            "engine": "mock",
            "voice_profile": "jarvis",
            "speed": 1.0,
            "pitch_shift": 0,
            "piper_model": "en_US-lessac-medium",
        },
        "wake_word": {
            "model_path": None,
            "threshold": 0.5,
            "vad_threshold": 0.5,
        },
        "claude": {
            "model": "claude-sonnet-4-6",
            "max_tokens": 300,
            "temperature": 0.7,
            "max_history_turns": 10,
        },
        "agents": {
            "orchestrator_model": "claude-opus-4-5",
            "subagent_model": "claude-sonnet-4-6",
            "orchestrator_max_tokens": 150,
            "chat_max_tokens": 300,
            "action_max_tokens": 100,
            "skip_orchestrator_on_clear_intent": True,
            "history_turns_for_chat": 10,
            "history_turns_for_orchestrator": 3,
        },
        "pc_control": {
            "enabled": True,
            "platform": "auto",
        },
        "smart_home": {
            "enabled": False,
        },
        "api": {
            "ws_port": 8765,
            "http_port": 8766,
            "cors_origins": ["http://localhost:5173"],
        },
        "logging": {
            "level": "DEBUG",
            "file": None,
        },
        "anthropic_api_key": "test-api-key",
        "home_assistant_url": "http://homeassistant.local:8123",
        "home_assistant_token": "test-token",
    }


@pytest.fixture
def sample_audio_bytes():
    """Return sample 16kHz PCM audio bytes for testing."""
    # Generate 1 second of silence at 16kHz, 16-bit mono
    sample_rate = 16000
    duration = 1.0
    samples = int(sample_rate * duration)

    # Create silent audio with some minor noise
    audio = np.random.randint(-100, 100, samples, dtype=np.int16)

    return audio.tobytes()


@pytest.fixture
def sample_speech_audio_bytes():
    """Return sample audio with simulated speech (sine wave)."""
    sample_rate = 16000
    duration = 2.0
    samples = int(sample_rate * duration)
    t = np.linspace(0, duration, samples)

    # Generate a 440Hz tone to simulate speech
    freq = 440
    audio = (np.sin(2 * np.pi * freq * t) * 16000).astype(np.int16)

    return audio.tobytes()


@pytest.fixture
def sample_audio_numpy():
    """Return sample audio as numpy float32 array."""
    sample_rate = 16000
    duration = 1.0
    samples = int(sample_rate * duration)

    # Create audio with minor noise
    audio = np.random.uniform(-0.01, 0.01, samples).astype(np.float32)

    return audio


class MockConfigLoader:
    """Mock ConfigLoader for testing."""

    def __init__(self, config: dict):
        self._config = config

    def get(self, key: str, default=None):
        """Get a configuration value by dot-notation key."""
        keys = key.split(".")
        value = self._config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def get_section(self, section: str) -> dict:
        """Get an entire configuration section."""
        return self._config.get(section, {})

    @property
    def is_rpi(self) -> bool:
        """Check if running on Raspberry Pi."""
        return False


@pytest.fixture
def mock_config_loader(mock_config):
    """Return a mock ConfigLoader instance."""
    return MockConfigLoader(mock_config)
