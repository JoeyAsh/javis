"""Base agent class for JARVIS subagents."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from utils.config_loader import get_config
from utils.logger import get_logger

logger = get_logger("agent.base")


@dataclass
class AgentResult:
    """Result from an agent execution."""

    spoken_response: str
    success: bool = True
    data: dict[str, Any] = field(default_factory=dict)


class BaseAgent(ABC):
    """Abstract base class for all JARVIS agents."""

    # Default model for subagents
    model: str = "claude-sonnet-4-6"

    def __init__(self) -> None:
        """Initialize the base agent."""
        cfg = get_config()
        agents_config = cfg.get_section("agents")
        self.model = agents_config.get("subagent_model", "claude-sonnet-4-6")
        self.max_tokens = agents_config.get("action_max_tokens", 100)

    @abstractmethod
    async def run(
        self, task: str, params: dict[str, Any], language: str
    ) -> AgentResult:
        """Execute the agent's task.

        Args:
            task: Task description or user input
            params: Parameters extracted by intent parser or orchestrator
            language: Response language (en, de)

        Returns:
            AgentResult with spoken response and execution data
        """
        pass

    def _get_language_instruction(self, language: str) -> str:
        """Get language instruction for system prompt.

        Args:
            language: Language code (en, de)

        Returns:
            Language instruction string
        """
        if language == "de":
            return "Respond in German (Deutsch)."
        return "Respond in English."

    def _format_error_response(self, error: str, language: str) -> str:
        """Format an error response in the appropriate language.

        Args:
            error: Error message
            language: Language code

        Returns:
            Formatted error response
        """
        if language == "de":
            return f"Es tut mir leid, Sir, aber es gab ein Problem: {error}"
        return f"I apologize, sir, but there was an issue: {error}"
