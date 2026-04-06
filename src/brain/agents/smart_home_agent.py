"""Smart home agent for JARVIS."""

from typing import Any

from actions.smart_home import execute_home_action
from brain.agents.base import AgentResult, BaseAgent
from brain.claude_client import ClaudeClient
from utils.config_loader import get_config
from utils.logger import get_logger

logger = get_logger("agent.smart_home")


class SmartHomeAgent(BaseAgent):
    """Agent for smart home control via Home Assistant."""

    def __init__(self, claude_client: ClaudeClient) -> None:
        """Initialize the smart home agent.

        Args:
            claude_client: Claude client for API calls
        """
        super().__init__()
        self.claude_client = claude_client

        cfg = get_config()
        self.enabled = cfg.get("smart_home.enabled", False)

    async def run(
        self, task: str, params: dict[str, Any], language: str
    ) -> AgentResult:
        """Execute a smart home action.

        Args:
            task: Task description
            params: Action parameters (domain, action, room, etc.)
            language: Response language

        Returns:
            AgentResult with confirmation message
        """
        # Check if smart home is enabled
        if not self.enabled:
            if language == "de":
                msg = "Smart Home ist nicht konfiguriert, Sir. Bitte aktivieren Sie es in der Konfiguration."
            else:
                msg = "Smart home is not configured, sir. Please enable it in the configuration."
            return AgentResult(
                spoken_response=msg,
                success=False,
                data={"reason": "disabled"},
            )

        try:
            action = params.get("action", "unknown")
            domain = params.get("domain", "light")

            # Execute the action
            result = await execute_home_action(params)

            # Check for errors
            if "error" in result.lower() or "unavailable" in result.lower():
                return AgentResult(
                    spoken_response=result,
                    success=False,
                    data={"action": action, "error": result},
                )

            # Generate spoken response
            response = self._generate_response(action, domain, params, language)

            return AgentResult(
                spoken_response=response,
                success=True,
                data={"action": action, "domain": domain, "result": result},
            )

        except Exception as e:
            logger.error(f"Smart home agent error: {e}")
            return AgentResult(
                spoken_response=self._format_error_response(str(e), language),
                success=False,
                data={"error": str(e)},
            )

    def _generate_response(
        self, action: str, domain: str, params: dict[str, Any], language: str
    ) -> str:
        """Generate a spoken response for the action.

        Args:
            action: Action type
            domain: Device domain (light, climate, lock)
            params: Action parameters
            language: Response language

        Returns:
            Spoken response string
        """
        room = params.get("room", "")
        room_str = f" in the {room.replace('_', ' ')}" if room else ""
        room_str_de = f" im {room.replace('_', ' ')}" if room else ""

        if domain == "light":
            responses = {
                "turn_on": {
                    "en": f"Lights{room_str} turned on, sir.",
                    "de": f"Licht{room_str_de} eingeschaltet, Sir.",
                },
                "turn_off": {
                    "en": f"Lights{room_str} turned off, sir.",
                    "de": f"Licht{room_str_de} ausgeschaltet, Sir.",
                },
                "toggle": {
                    "en": f"Lights{room_str} toggled, sir.",
                    "de": f"Licht{room_str_de} umgeschaltet, Sir.",
                },
                "dim": {
                    "en": f"Lights{room_str} dimmed to {params.get('brightness', 50)}%, sir.",
                    "de": f"Licht{room_str_de} auf {params.get('brightness', 50)}% gedimmt, Sir.",
                },
            }
        elif domain == "climate":
            responses = {
                "set_temperature": {
                    "en": f"Temperature{room_str} set to {params.get('temperature', 21)} degrees, sir.",
                    "de": f"Temperatur{room_str_de} auf {params.get('temperature', 21)} Grad gesetzt, Sir.",
                },
            }
        elif domain == "lock":
            responses = {
                "lock": {
                    "en": f"Door{room_str} locked, sir.",
                    "de": f"Tür{room_str_de} abgeschlossen, Sir.",
                },
                "unlock": {
                    "en": f"Door{room_str} unlocked, sir.",
                    "de": f"Tür{room_str_de} aufgeschlossen, Sir.",
                },
            }
        else:
            responses = {}

        action_responses = responses.get(action, {})
        default = "Action completed, sir." if language == "en" else "Aktion ausgeführt, Sir."
        return action_responses.get(language, default)
