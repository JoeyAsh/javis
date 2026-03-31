"""Chat agent for JARVIS - handles general conversation."""

from typing import Any

from src.brain.agents.base import AgentResult, BaseAgent
from src.brain.claude_client import ClaudeClient
from src.brain.memory import ConversationMemory
from src.utils.config_loader import get_config
from src.utils.logger import get_logger

logger = get_logger("agent.chat")

CHAT_SYSTEM_PROMPT = """You are JARVIS (Just A Rather Very Intelligent System).
Calm, precise, slightly formal, dry wit. Address user as "sir" or "ma'am".
Respond in 1-3 sentences unless asked for detail.
Always respond in the same language the user spoke.
You are helpful, knowledgeable, and maintain a professional demeanor with subtle humor."""


class ChatAgent(BaseAgent):
    """Agent for general conversation and Q&A."""

    def __init__(
        self, claude_client: ClaudeClient, memory: ConversationMemory
    ) -> None:
        """Initialize the chat agent.

        Args:
            claude_client: Claude client for API calls
            memory: Conversation memory for context
        """
        super().__init__()
        self.claude_client = claude_client
        self.memory = memory

        cfg = get_config()
        agents_config = cfg.get_section("agents")
        self.max_tokens = agents_config.get("chat_max_tokens", 300)
        self.history_turns = agents_config.get("history_turns_for_chat", 10)

    async def run(
        self, task: str, params: dict[str, Any], language: str
    ) -> AgentResult:
        """Handle a chat request.

        Args:
            task: User message
            params: Additional parameters (unused for chat)
            language: Response language

        Returns:
            AgentResult with JARVIS response
        """
        try:
            # Get conversation history
            history = self.memory.get_history(self.history_turns)

            # Build system prompt with language instruction
            system_prompt = CHAT_SYSTEM_PROMPT
            system_prompt += f"\n\n{self._get_language_instruction(language)}"

            # Get response from Claude
            response = await self.claude_client.complete(
                prompt=task,
                system_prompt=system_prompt,
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=0.7,
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
