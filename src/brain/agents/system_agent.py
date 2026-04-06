"""System agent for JARVIS - handles system commands."""

from pathlib import Path
from typing import Any

from brain.agents.base import AgentResult, BaseAgent
from brain.claude_client import ClaudeClient
from brain.memory import ConversationMemory
from utils.logger import get_logger

logger = get_logger("agent.system")


class SystemAgent(BaseAgent):
    """Agent for JARVIS system commands."""

    # Flag to signal shutdown
    shutdown_requested: bool = False

    def __init__(
        self,
        claude_client: ClaudeClient,
        memory: ConversationMemory,
        tts_engine: Any = None,
    ) -> None:
        """Initialize the system agent.

        Args:
            claude_client: Claude client for API calls
            memory: Conversation memory
            tts_engine: TTS engine for voice changes
        """
        super().__init__()
        self.claude_client = claude_client
        self.memory = memory
        self.tts_engine = tts_engine

    async def run(
        self, task: str, params: dict[str, Any], language: str
    ) -> AgentResult:
        """Execute a system action.

        Args:
            task: Task description
            params: Action parameters
            language: Response language

        Returns:
            AgentResult with confirmation message
        """
        action = params.get("action", "unknown")

        try:
            if action == "shutdown":
                return await self._shutdown(language)
            elif action == "change_voice":
                voice = params.get("voice")
                return await self._change_voice(voice, language)
            elif action == "reset_memory":
                return await self._reset_memory(language)
            elif action == "list_voices":
                return await self._list_voices(language)
            else:
                # Unknown action
                if language == "de":
                    msg = "Ich habe diese Systemanfrage nicht verstanden, Sir."
                else:
                    msg = "I didn't understand that system request, sir."
                return AgentResult(
                    spoken_response=msg,
                    success=False,
                    data={"action": action, "reason": "unknown_action"},
                )

        except Exception as e:
            logger.error(f"System agent error: {e}")
            return AgentResult(
                spoken_response=self._format_error_response(str(e), language),
                success=False,
                data={"error": str(e)},
            )

    async def _shutdown(self, language: str) -> AgentResult:
        """Handle shutdown request.

        Args:
            language: Response language

        Returns:
            AgentResult with goodbye message
        """
        SystemAgent.shutdown_requested = True

        if language == "de":
            msg = "System wird heruntergefahren. Auf Wiedersehen, Sir."
        else:
            msg = "Shutting down. Goodbye, sir."

        logger.info("Shutdown requested by user")

        return AgentResult(
            spoken_response=msg,
            success=True,
            data={"action": "shutdown"},
        )

    async def _change_voice(self, voice: str | None, language: str) -> AgentResult:
        """Change the TTS voice profile.

        Args:
            voice: Voice profile name
            language: Response language

        Returns:
            AgentResult with confirmation
        """
        if self.tts_engine is None:
            if language == "de":
                msg = "TTS-Engine ist nicht verfügbar, Sir."
            else:
                msg = "TTS engine is not available, sir."
            return AgentResult(
                spoken_response=msg,
                success=False,
                data={"reason": "no_tts"},
            )

        # Get available voices
        voices = self._get_available_voices()

        if not voice:
            # No voice specified, list available
            if language == "de":
                msg = f"Welche Stimme soll ich verwenden, Sir? Verfügbar sind: {', '.join(voices)}"
            else:
                msg = f"Which voice should I use, sir? Available: {', '.join(voices)}"
            return AgentResult(
                spoken_response=msg,
                success=True,
                data={"available_voices": voices},
            )

        # Check if voice exists
        voice_lower = voice.lower()
        matching_voice = None
        for v in voices:
            if v.lower() == voice_lower or v.lower().startswith(voice_lower):
                matching_voice = v
                break

        if not matching_voice:
            if language == "de":
                msg = f"Stimme '{voice}' nicht gefunden, Sir. Verfügbar: {', '.join(voices)}"
            else:
                msg = f"Voice '{voice}' not found, sir. Available: {', '.join(voices)}"
            return AgentResult(
                spoken_response=msg,
                success=False,
                data={"available_voices": voices},
            )

        # Change voice
        if hasattr(self.tts_engine, "set_voice_profile"):
            self.tts_engine.set_voice_profile(matching_voice)

        if language == "de":
            msg = f"Stimme auf {matching_voice} gewechselt, Sir."
        else:
            msg = f"Voice changed to {matching_voice}, sir."

        logger.info(f"Voice changed to: {matching_voice}")

        return AgentResult(
            spoken_response=msg,
            success=True,
            data={"voice": matching_voice},
        )

    async def _reset_memory(self, language: str) -> AgentResult:
        """Reset conversation memory.

        Args:
            language: Response language

        Returns:
            AgentResult with confirmation
        """
        self.memory.clear()

        if language == "de":
            msg = "Gesprächsspeicher zurückgesetzt, Sir. Wir beginnen von vorn."
        else:
            msg = "Conversation memory cleared, sir. Starting fresh."

        logger.info("Conversation memory reset by user")

        return AgentResult(
            spoken_response=msg,
            success=True,
            data={"action": "reset_memory"},
        )

    async def _list_voices(self, language: str) -> AgentResult:
        """List available voice profiles.

        Args:
            language: Response language

        Returns:
            AgentResult with voice list
        """
        voices = self._get_available_voices()

        if not voices:
            if language == "de":
                msg = "Keine Stimmprofile gefunden, Sir."
            else:
                msg = "No voice profiles found, sir."
            return AgentResult(
                spoken_response=msg,
                success=False,
                data={"voices": []},
            )

        voices_str = ", ".join(voices)
        if language == "de":
            msg = f"Verfügbare Stimmen: {voices_str}"
        else:
            msg = f"Available voices: {voices_str}"

        return AgentResult(
            spoken_response=msg,
            success=True,
            data={"voices": voices},
        )

    def _get_available_voices(self) -> list[str]:
        """Get list of available voice profiles.

        Returns:
            List of voice profile names
        """
        voices_dir = Path(__file__).parent.parent.parent.parent / "voices"
        if not voices_dir.exists():
            return []

        voices = []
        for wav_file in voices_dir.glob("*.wav"):
            if wav_file.stem != "chime":  # Exclude chime sound
                voices.append(wav_file.stem)

        return sorted(voices)
