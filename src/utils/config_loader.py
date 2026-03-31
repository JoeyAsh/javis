"""Configuration loader for JARVIS.

Loads configuration from YAML files and environment variables.
"""

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


class ConfigLoader:
    """Loads and manages JARVIS configuration.

    Supports loading from YAML files with environment variable overrides.
    Automatically detects Raspberry Pi platform and adjusts settings.
    """

    _instance: "ConfigLoader | None" = None
    _config: dict[str, Any] = {}

    def __new__(cls) -> "ConfigLoader":
        """Singleton pattern for global config access."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize the config loader."""
        if not self._config:
            self._load()

    def _load(self) -> None:
        """Load configuration from files and environment."""
        # Load .env file
        load_dotenv()

        # Determine config path
        config_path = Path(__file__).parent.parent.parent / "config" / "config.yaml"

        # Load YAML config
        if config_path.exists():
            with open(config_path) as f:
                self._config = yaml.safe_load(f) or {}
        else:
            self._config = self._get_default_config()

        # Apply platform-specific overrides
        self._apply_platform_overrides()

        # Apply environment variable overrides
        self._apply_env_overrides()

    def _get_default_config(self) -> dict[str, Any]:
        """Return default configuration."""
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
                "model": "large-v3",
                "device": "cuda",
                "compute_type": "float16",
                "language": None,
            },
            "tts": {
                "engine": "xtts",
                "voice_profile": "jarvis",
                "speed": 1.0,
                "pitch_shift": 0,
                "piper_model": "en_US-lessac-medium",
            },
            "wake_word": {
                "model_path": "wake_word/jarvis.onnx",
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
                "level": "INFO",
                "file": "logs/jarvis.log",
            },
        }

    def _is_raspberry_pi(self) -> bool:
        """Detect if running on Raspberry Pi."""
        # Check environment variable first
        if os.environ.get("JARVIS_PLATFORM") == "rpi":
            return True

        # Check for Raspberry Pi hardware
        try:
            with open("/proc/cpuinfo") as f:
                cpuinfo = f.read()
                return "Raspberry Pi" in cpuinfo or "BCM" in cpuinfo
        except (FileNotFoundError, PermissionError):
            return False

    def _apply_platform_overrides(self) -> None:
        """Apply platform-specific configuration overrides."""
        if self._is_raspberry_pi():
            # STT: downgrade for RPi
            self._config.setdefault("stt", {})
            self._config["stt"]["model"] = "small"
            self._config["stt"]["device"] = "cpu"
            self._config["stt"]["compute_type"] = "int8"

            # TTS: use Piper on RPi
            self._config.setdefault("tts", {})
            self._config["tts"]["engine"] = "piper"

            # Disable PC control on RPi
            self._config.setdefault("pc_control", {})
            self._config["pc_control"]["enabled"] = False

    def _apply_env_overrides(self) -> None:
        """Apply environment variable overrides."""
        # API keys are only loaded from environment
        self._config["anthropic_api_key"] = os.environ.get("ANTHROPIC_API_KEY", "")
        self._config["home_assistant_url"] = os.environ.get(
            "HOME_ASSISTANT_URL", "http://homeassistant.local:8123"
        )
        self._config["home_assistant_token"] = os.environ.get(
            "HOME_ASSISTANT_TOKEN", ""
        )

        # Override logging level from env
        if log_level := os.environ.get("JARVIS_LOG_LEVEL"):
            self._config.setdefault("logging", {})
            self._config["logging"]["level"] = log_level

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value by dot-notation key.

        Args:
            key: Configuration key in dot notation (e.g., "audio.sample_rate")
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        keys = key.split(".")
        value = self._config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def get_section(self, section: str) -> dict[str, Any]:
        """Get an entire configuration section.

        Args:
            section: Section name (e.g., "audio", "stt")

        Returns:
            Configuration section as dictionary
        """
        return self._config.get(section, {})

    @property
    def is_rpi(self) -> bool:
        """Check if running on Raspberry Pi."""
        return self._is_raspberry_pi()

    def reload(self) -> None:
        """Reload configuration from files."""
        self._config = {}
        self._load()


# Global config instance
_config: ConfigLoader | None = None


def get_config() -> ConfigLoader:
    """Get the global configuration instance.

    Returns:
        ConfigLoader instance
    """
    global _config
    if _config is None:
        _config = ConfigLoader()
    return _config
