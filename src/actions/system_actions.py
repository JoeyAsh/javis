"""System actions for JARVIS.

Provides high-level system action functions used by the system agent.
"""

from pathlib import Path
from typing import Any

from src.brain.memory import ConversationMemory
from src.utils.config_loader import get_config
from src.utils.logger import get_logger

logger = get_logger("system_actions")


class SystemActions:
    """High-level system actions for JARVIS."""

    def __init__(
        self,
        memory: ConversationMemory,
        tts_engine: Any = None,
    ) -> None:
        """Initialize system actions.

        Args:
            memory: Conversation memory
            tts_engine: TTS engine instance
        """
        self.memory = memory
        self.tts_engine = tts_engine
        self._shutdown_requested = False

    async def change_voice(self, profile: str) -> tuple[bool, str]:
        """Change the TTS voice profile.

        Args:
            profile: Voice profile name

        Returns:
            Tuple of (success, message)
        """
        if self.tts_engine is None:
            return False, "TTS engine not available"

        available = self.list_voices()

        # Find matching voice
        profile_lower = profile.lower()
        matching = None
        for v in available:
            if v.lower() == profile_lower or v.lower().startswith(profile_lower):
                matching = v
                break

        if not matching:
            return False, f"Voice '{profile}' not found. Available: {', '.join(available)}"

        # Change voice
        if hasattr(self.tts_engine, "set_voice_profile"):
            self.tts_engine.set_voice_profile(matching)
            logger.info(f"Voice changed to: {matching}")
            return True, f"Voice changed to {matching}"
        else:
            return False, "TTS engine does not support voice profiles"

    async def reset_memory(self) -> tuple[bool, str]:
        """Reset conversation memory.

        Returns:
            Tuple of (success, message)
        """
        self.memory.clear()
        logger.info("Conversation memory reset")
        return True, "Conversation memory cleared"

    async def shutdown(self) -> tuple[bool, str]:
        """Request system shutdown.

        Returns:
            Tuple of (success, message)
        """
        self._shutdown_requested = True
        logger.info("Shutdown requested")
        return True, "Shutdown initiated"

    def list_voices(self) -> list[str]:
        """List available voice profiles.

        Returns:
            List of voice profile names
        """
        voices_dir = Path(__file__).parent.parent.parent / "voices"
        if not voices_dir.exists():
            return []

        voices = []
        for wav_file in voices_dir.glob("*.wav"):
            if wav_file.stem != "chime":
                voices.append(wav_file.stem)

        return sorted(voices)

    @property
    def shutdown_requested(self) -> bool:
        """Check if shutdown has been requested."""
        return self._shutdown_requested

    def set_tts_engine(self, tts_engine: Any) -> None:
        """Set the TTS engine.

        Args:
            tts_engine: TTS engine instance
        """
        self.tts_engine = tts_engine


async def get_system_info() -> dict[str, Any]:
    """Get current system information.

    Returns:
        Dictionary with system metrics
    """
    import psutil

    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    boot_time = psutil.boot_time()

    # Calculate uptime
    import time

    uptime_seconds = int(time.time() - boot_time)
    hours = uptime_seconds // 3600
    minutes = (uptime_seconds % 3600) // 60

    if hours > 0:
        uptime_str = f"{hours}h {minutes}m"
    else:
        uptime_str = f"{minutes}m"

    return {
        "cpu": round(cpu_percent, 1),
        "mem": round(memory.percent, 1),
        "uptime": uptime_str,
        "uptime_seconds": uptime_seconds,
    }
