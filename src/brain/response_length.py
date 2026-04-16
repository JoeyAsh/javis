"""Response length control for JARVIS.

Ensures responses are concise (1-3 sentences) unless the user
explicitly requests detail.

Example usage:
    from brain.response_length import ResponseLengthController

    controller = ResponseLengthController()

    # Check if user wants detail
    if controller.check_detail_request(user_text):
        # Allow longer response
        pass

    # Get system prompt modifier
    modifier = controller.get_length_modifier()
    system_prompt = base_prompt + modifier
"""

from __future__ import annotations

import re

from utils.logger import get_logger

logger = get_logger("response_length")

# System prompt modifier for concise responses
CONCISE_MODIFIER = """
RESPONSE LENGTH: Keep responses to 2 sentences or fewer unless the user explicitly
asks for detail (phrases like "tell me more", "explain more", "details please",
"expand on that", "erklär mir mehr", "mehr details", "genauer"). When detail is
requested, you may use up to 5 sentences.
"""

# Patterns that request more detail
DETAIL_TRIGGERS = [
    # English
    r"\b(more detail|expand|elaborate|tell me more|explain more)\b",
    r"\b(go on|continue|keep going|and then)\b",
    r"\b(why is that|how so|in what way)\b",
    # German
    r"\b(mehr detail|erklär mir mehr|details bitte|genauer)\b",
    r"\b(erzähl weiter|und dann|wie das|warum das)\b",
]


class ResponseLengthController:
    """Control response length based on user requests.

    Tracks whether the user has requested detail and provides
    appropriate system prompt modifiers.

    Attributes:
        detail_mode: Whether currently in detail mode.
    """

    def __init__(self) -> None:
        """Initialize response length controller."""
        self._detail_patterns = [
            re.compile(p, re.IGNORECASE) for p in DETAIL_TRIGGERS
        ]
        self._detail_mode = False

    @property
    def detail_mode(self) -> bool:
        """Check if in detail mode."""
        return self._detail_mode

    def check_detail_request(self, text: str) -> bool:
        """Check if user is requesting more detail.

        Updates internal state and returns result.

        Args:
            text: User input text.

        Returns:
            True if detail was requested.
        """
        self._detail_mode = any(p.search(text) for p in self._detail_patterns)

        if self._detail_mode:
            logger.debug("Detail mode activated")

        return self._detail_mode

    def get_length_modifier(self) -> str:
        """Get system prompt modifier for current mode.

        Returns:
            Empty string in detail mode, CONCISE_MODIFIER otherwise.
        """
        if self._detail_mode:
            return ""  # No restriction in detail mode
        return CONCISE_MODIFIER

    def reset(self) -> None:
        """Reset to default (concise) mode."""
        self._detail_mode = False

    def force_detail_mode(self, enabled: bool) -> None:
        """Force detail mode on or off.

        Args:
            enabled: Whether to enable detail mode.
        """
        self._detail_mode = enabled


class ResponseFormatter:
    """Format responses for voice output.

    Ensures responses are clean and suitable for TTS.
    """

    def __init__(self) -> None:
        """Initialize response formatter."""
        pass

    def format_for_speech(self, text: str) -> str:
        """Format text for TTS output.

        Removes markdown and ensures natural speech flow.

        Args:
            text: Raw response text.

        Returns:
            Cleaned text suitable for TTS.
        """
        # Remove code blocks
        text = re.sub(r"```[\s\S]*?```", "", text)
        # Remove inline backticks
        text = re.sub(r"`[^`]*`", "", text)
        # Remove bold/italic markers
        text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)
        # Remove headers
        text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
        # Convert links to text only
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        # Remove bullet/numbered list markers
        text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
        text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)
        # Replace multiple newlines with period + space
        text = re.sub(r"\n{2,}", ". ", text)
        # Replace single newlines with space
        text = re.sub(r"\n", " ", text)
        # Collapse multiple spaces
        text = re.sub(r" {2,}", " ", text).strip()

        return text

    def truncate_sentences(self, text: str, max_sentences: int = 3) -> str:
        """Truncate text to maximum sentences.

        Args:
            text: Text to truncate.
            max_sentences: Maximum sentences to keep.

        Returns:
            Truncated text.
        """
        # Simple sentence splitting
        sentences = re.split(r"(?<=[.!?])\s+", text)
        if len(sentences) <= max_sentences:
            return text

        truncated = " ".join(sentences[:max_sentences])

        # Ensure ends with punctuation
        if truncated and truncated[-1] not in ".!?":
            truncated += "."

        return truncated
