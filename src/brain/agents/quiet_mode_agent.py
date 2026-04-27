"""QuietModeAgent — handles QUIET_MODE_ON / QUIET_MODE_OFF intents (#93 Phase 2).

Receives the two quiet-mode intents from the orchestrator, calls the shared
NarrationQueue's ``set_quiet_mode`` method, and returns a spoken acknowledgment
in JARVIS persona (German or English depending on the turn language).
"""

from __future__ import annotations

from typing import Any

from brain.agents.base import AgentResult, BaseAgent
from utils.config_loader import get_config
from utils.logger import get_logger

logger = get_logger("agent.quiet_mode")


class QuietModeAgent(BaseAgent):
    """Handles quiet-mode voice intents and delegates to the NarrationQueue."""

    def __init__(self, narration_queue: Any) -> None:
        """Initialise the agent.

        Args:
            narration_queue: The shared :class:`brain.narration_queue.NarrationQueue`
                instance, or None when not yet initialised. The agent will still
                return a graceful error response when the queue is None.
        """
        super().__init__()
        self._narration_queue = narration_queue

    async def run(
        self,
        task: str,
        params: dict[str, Any],
        language: str,
    ) -> AgentResult:
        """Execute the quiet-mode intent.

        Dispatches on ``params["action"]``: ``"on"`` or ``"off"``.

        Args:
            task: Original STT utterance (unused — action is in params).
            params: Dict with key ``action`` (``"on"`` or ``"off"``) and
                optional ``duration_minutes`` for quiet-on.
            language: Turn language (``"en"`` or ``"de"``).

        Returns:
            :class:`AgentResult` with a JARVIS-style spoken acknowledgment.
        """
        action: str = params.get("action", "on")
        duration: int | None = params.get("duration_minutes")

        if self._narration_queue is None:
            logger.warning("QuietModeAgent: NarrationQueue not available")
            response = (
                "Entschuldigung, Sir — der Stille-Modus ist noch nicht verfügbar."
                if language == "de"
                else "Apologies, Sir — quiet mode is not available yet."
            )
            return AgentResult(spoken_response=response, success=False)

        if action == "off":
            self._narration_queue.set_quiet_mode(enabled=False)
            response = self._ack_off(language)
            logger.info("QuietModeAgent: quiet mode disabled")
        else:
            # Determine duration: use param, then config default, then 60.
            if duration is None:
                try:
                    cfg = get_config()
                    narration_cfg = cfg.get_section("narration") or {}
                    duration = int(narration_cfg.get("quiet_mode_default_minutes", 60))
                except Exception:
                    duration = 60

            self._narration_queue.set_quiet_mode(enabled=True, duration_minutes=duration)
            response = self._ack_on(duration, language)
            logger.info(f"QuietModeAgent: quiet mode enabled for {duration}min")

        return AgentResult(spoken_response=response, success=True)

    @staticmethod
    def _ack_on(duration: int, language: str) -> str:
        """Return the spoken acknowledgment for quiet-mode activation.

        Args:
            duration: Duration in minutes.
            language: Turn language.

        Returns:
            JARVIS acknowledgment string.
        """
        if language == "de":
            return (
                f"Verstanden, Sir — ich halte mich für {duration} Minuten zurück."
            )
        return f"Understood, Sir — I'll keep quiet for {duration} minutes."

    @staticmethod
    def _ack_off(language: str) -> str:
        """Return the spoken acknowledgment for quiet-mode deactivation.

        Args:
            language: Turn language.

        Returns:
            JARVIS acknowledgment string.
        """
        if language == "de":
            return "Wieder zur Verfügung, Sir."
        return "Back at your service, Sir."
