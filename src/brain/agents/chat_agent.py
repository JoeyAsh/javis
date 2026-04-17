"""Chat agent for JARVIS - handles general conversation.

Conversational turns now route through OpenClaw via
:class:`brain.claude_client.ClaudeClient`. OpenClaw owns:
- the persona (loaded from ``~/.openclaw/workspace/SOUL.md``),
- the multi-turn session memory (pinned to ``config.openclaw.session_id``).

This agent therefore no longer injects a JARVIS system prompt or passes
``ConversationMemory`` history — doing so would double-prompt OpenClaw
and fragment session state. The ``ConversationMemory`` argument is kept
in the constructor for backward compatibility (the ``SystemAgent`` still
exposes a ``reset memory`` command that clears the local archive), but
it is not consulted during a conversational turn.
"""

from typing import Any

from brain.agents.base import AgentResult, BaseAgent
from brain.claude_client import ClaudeClient
from brain.memory_legacy import ConversationMemory
from utils.logger import get_logger

logger = get_logger("agent.chat")


class ChatAgent(BaseAgent):
    """Agent for general conversation and Q&A."""

    def __init__(
        self, claude_client: ClaudeClient, memory: ConversationMemory
    ) -> None:
        """Initialize the chat agent.

        Args:
            claude_client: OpenClaw-backed LLM client.
            memory: Legacy in-RAM conversation buffer. Retained so the
                ``reset memory`` system command has something to clear;
                NOT consulted for LLM context — OpenClaw owns that now.
        """
        super().__init__()
        self.claude_client = claude_client
        self.memory = memory

    async def run(
        self, task: str, params: dict[str, Any], language: str
    ) -> AgentResult:
        """Handle a chat request.

        Args:
            task: User message.
            params: Additional parameters (unused for chat).
            language: Response language (``"en"``/``"de"``).

        Returns:
            AgentResult with JARVIS's response.
        """
        del params  # Unused for general chat.

        try:
            # Go straight to OpenClaw. Persona + history live there.
            response = await self.claude_client.chat(
                message=task,
                language=language,
            )

            if not response:
                response = self._format_error_response(
                    "I couldn't formulate a response", language
                )

            logger.debug(f"Chat response: {response[:100]}...")

            return AgentResult(
                spoken_response=response,
                success=True,
                data={"type": "chat"},
            )

        except Exception as e:
            logger.error(f"Chat agent error: {e}")
            return AgentResult(
                spoken_response=self._format_error_response(str(e), language),
                success=False,
                data={"error": str(e)},
            )
