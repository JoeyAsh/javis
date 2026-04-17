"""Chat agent for JARVIS — thin wrapper around the OpenClaw chat path.

All conversational turns route through OpenClaw via
:class:`brain.claude_client.ClaudeClient`. OpenClaw owns:
- the persona (loaded from ``~/.openclaw/workspace/SOUL.md``),
- the multi-turn session memory (pinned to ``config.openclaw.session_id``).

This agent does not build prompts, maintain history, or inject a system
prompt — OpenClaw would double-prompt. The legacy ``ConversationMemory``
field has been removed entirely: the archive of transcripts lives in
:class:`brain.memory.MemoryStore` and short-term context lives inside
OpenClaw's session store.
"""

from typing import Any

from brain.agents.base import AgentResult, BaseAgent
from brain.claude_client import ClaudeClient
from utils.logger import get_logger

logger = get_logger("agent.chat")


class ChatAgent(BaseAgent):
    """Agent for general conversation and Q&A (OpenClaw-backed)."""

    def __init__(self, claude_client: ClaudeClient) -> None:
        """Initialise the chat agent.

        Args:
            claude_client: OpenClaw-backed LLM client.
        """
        super().__init__()
        self.claude_client = claude_client

    async def run(
        self, task: str, params: dict[str, Any], language: str
    ) -> AgentResult:
        """Handle a chat request.

        Args:
            task: User message.
            params: Additional parameters (unused for chat).
            language: Response language (``"en"``/``"de"``).

        Returns:
            ``AgentResult`` with JARVIS's response.
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
