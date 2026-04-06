"""Conversation memory for JARVIS.

Manages conversation history for context in LLM calls.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from utils.logger import get_logger

logger = get_logger("memory")


@dataclass
class ConversationTurn:
    """A single turn in the conversation."""

    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    language: str = "en"
    metadata: dict[str, Any] = field(default_factory=dict)


class ConversationMemory:
    """In-memory conversation history manager."""

    def __init__(self, max_turns: int = 10) -> None:
        """Initialize conversation memory.

        Args:
            max_turns: Maximum number of turns to keep
        """
        self.max_turns = max_turns
        self._history: list[ConversationTurn] = []

    def add_turn(
        self,
        role: str,
        content: str,
        language: str = "en",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Add a turn to conversation history.

        Args:
            role: "user" or "assistant"
            content: Message content
            language: Language of the message
            metadata: Optional metadata
        """
        turn = ConversationTurn(
            role=role,
            content=content,
            language=language,
            metadata=metadata or {},
        )
        self._history.append(turn)

        # Trim to max turns
        if len(self._history) > self.max_turns * 2:  # Store pairs
            self._history = self._history[-(self.max_turns * 2) :]

        logger.debug(f"Added turn: {role} ({len(content)} chars)")

    def get_history(
        self, num_turns: int | None = None
    ) -> list[dict[str, str]]:
        """Get conversation history for LLM context.

        Args:
            num_turns: Number of turn pairs to return. None returns all.

        Returns:
            List of message dicts with 'role' and 'content'
        """
        history = self._history
        if num_turns is not None:
            # Each turn pair = 2 messages (user + assistant)
            history = history[-(num_turns * 2) :]

        return [{"role": turn.role, "content": turn.content} for turn in history]

    def get_summary(self, num_turns: int = 3) -> str:
        """Get a brief summary of recent conversation.

        Args:
            num_turns: Number of recent turn pairs to summarize

        Returns:
            Summary string
        """
        recent = self._history[-(num_turns * 2) :]
        if not recent:
            return "No previous conversation."

        lines = []
        for turn in recent:
            role = "User" if turn.role == "user" else "JARVIS"
            # Truncate long messages
            content = turn.content[:100] + "..." if len(turn.content) > 100 else turn.content
            lines.append(f"{role}: {content}")

        return "\n".join(lines)

    def get_last_user_message(self) -> str | None:
        """Get the last user message.

        Returns:
            Last user message or None
        """
        for turn in reversed(self._history):
            if turn.role == "user":
                return turn.content
        return None

    def get_last_assistant_message(self) -> str | None:
        """Get the last assistant message.

        Returns:
            Last assistant message or None
        """
        for turn in reversed(self._history):
            if turn.role == "assistant":
                return turn.content
        return None

    def get_last_mentioned_entity(self, entity_type: str = "device") -> str | None:
        """Get the last mentioned entity for pronoun resolution.

        Args:
            entity_type: Type of entity to look for

        Returns:
            Last mentioned entity name or None
        """
        for turn in reversed(self._history):
            metadata = turn.metadata
            if entity_type in metadata:
                return metadata[entity_type]
        return None

    def clear(self) -> None:
        """Clear all conversation history."""
        self._history = []
        logger.info("Conversation memory cleared")

    @property
    def turn_count(self) -> int:
        """Get the number of turns in history."""
        return len(self._history) // 2

    @property
    def is_empty(self) -> bool:
        """Check if memory is empty."""
        return len(self._history) == 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize memory to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "max_turns": self.max_turns,
            "history": [
                {
                    "role": turn.role,
                    "content": turn.content,
                    "timestamp": turn.timestamp.isoformat(),
                    "language": turn.language,
                    "metadata": turn.metadata,
                }
                for turn in self._history
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConversationMemory":
        """Deserialize memory from dictionary.

        Args:
            data: Dictionary representation

        Returns:
            ConversationMemory instance
        """
        memory = cls(max_turns=data.get("max_turns", 10))
        for item in data.get("history", []):
            memory._history.append(
                ConversationTurn(
                    role=item["role"],
                    content=item["content"],
                    timestamp=datetime.fromisoformat(item["timestamp"]),
                    language=item.get("language", "en"),
                    metadata=item.get("metadata", {}),
                )
            )
        return memory
