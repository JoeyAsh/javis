"""PC control agent for JARVIS."""

from typing import Any

from actions.pc_control import execute_pc_action
from brain.agents.base import AgentResult, BaseAgent
from brain.claude_client import ClaudeClient
from utils.config_loader import get_config
from utils.logger import get_logger

logger = get_logger("agent.pc")


class PcAgent(BaseAgent):
    """Agent for PC control actions."""

    def __init__(self, claude_client: ClaudeClient) -> None:
        """Initialize the PC agent.

        Args:
            claude_client: Claude client for API calls
        """
        super().__init__()
        self.claude_client = claude_client

        cfg = get_config()
        self.enabled = cfg.get("pc_control.enabled", True)
        self.is_rpi = cfg.is_rpi

    async def run(
        self, task: str, params: dict[str, Any], language: str
    ) -> AgentResult:
        """Execute a PC control action.

        Args:
            task: Task description
            params: Action parameters (action, app, level, etc.)
            language: Response language

        Returns:
            AgentResult with confirmation message
        """
        # Check if PC control is enabled
        if not self.enabled or self.is_rpi:
            if language == "de":
                msg = "PC-Steuerung ist auf diesem Gerät nicht verfügbar, Sir."
            else:
                msg = "PC control is not available on this device, sir."
            return AgentResult(
                spoken_response=msg,
                success=False,
                data={"reason": "disabled"},
            )

        try:
            action = params.get("action", "unknown")

            # Execute the action
            result = await execute_pc_action(params)

            # Generate spoken response
            response = self._generate_response(action, params, result, language)

            return AgentResult(
                spoken_response=response,
                success=True,
                data={"action": action, "result": result},
            )

        except Exception as e:
            logger.error(f"PC agent error: {e}")
            return AgentResult(
                spoken_response=self._format_error_response(str(e), language),
                success=False,
                data={"error": str(e)},
            )

    def _generate_response(
        self, action: str, params: dict[str, Any], result: str, language: str
    ) -> str:
        """Generate a spoken response for the action.

        Args:
            action: Action type
            params: Action parameters
            result: Action result message
            language: Response language

        Returns:
            Spoken response string
        """
        responses = {
            "open_app": {
                "en": f"Opening {params.get('app_display', params.get('app', 'application'))}, sir.",
                "de": f"Öffne {params.get('app_display', params.get('app', 'Anwendung'))}, Sir.",
            },
            "close_app": {
                "en": f"Closing {params.get('app', 'application')}, sir.",
                "de": f"Schließe {params.get('app', 'Anwendung')}, Sir.",
            },
            "set_volume": {
                "en": f"Volume set to {params.get('level', 'adjusted')}, sir.",
                "de": f"Lautstärke auf {params.get('level', 'angepasst')} gesetzt, Sir.",
            },
            "mute_toggle": {
                "en": "Audio muted, sir." if "muted" in result.lower() else "Audio unmuted, sir.",
                "de": "Audio stummgeschaltet, Sir." if "muted" in result.lower() else "Audio aktiviert, Sir.",
            },
            "screenshot": {
                "en": "Screenshot captured, sir.",
                "de": "Screenshot aufgenommen, Sir.",
            },
            "type_text": {
                "en": "Text typed, sir.",
                "de": "Text eingegeben, Sir.",
            },
        }

        action_responses = responses.get(action, {})
        return action_responses.get(language, result)
