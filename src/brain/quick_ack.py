"""Quick acknowledgment generator for complex queries.

Emits a 1-word acknowledgment before substantive response for
complex questions, making JARVIS feel more responsive.

Example usage:
    from brain.quick_ack import QuickAckGenerator

    ack_gen = QuickAckGenerator(cache_dir)

    if ack_gen.should_ack(user_text):
        phrase, audio_path = ack_gen.get_ack("en")
        if audio_path.exists():
            await player.play(audio_path)
"""

from __future__ import annotations

import random
import re
from pathlib import Path

from utils.logger import get_logger

logger = get_logger("quick_ack")

# Patterns that warrant quick acknowledgment
COMPLEX_PATTERNS = [
    # English patterns
    r"\b(explain|describe|tell me about|how does|why is|what is the difference)\b",
    r"\b(can you|could you|would you).*(explain|describe|help me understand)\b",
    # German patterns
    r"\b(erklär|beschreib|erzähl|wie funktioniert|warum ist|was ist der unterschied)\b",
    r"\b(kannst du|könntest du).*(erklären|beschreiben)\b",
    # Multiple questions
    r"\?.*\?",
    # Long queries (more than 50 chars with question mark)
    r".{50,}\?",
]

# Acknowledgment phrases by language
ACK_PHRASES = {
    "de": ["Klar", "Verstanden", "Gut", "Ja"],
    "en": ["Right", "Got it", "Sure", "Yes"],
}


class QuickAckGenerator:
    """Generate quick acknowledgments for complex queries.

    Detects complex queries that warrant a quick "Got it" before
    the substantive response, reducing perceived latency.

    Attributes:
        cache_dir: Directory containing cached ack audio files.
    """

    def __init__(self, cache_dir: Path | str) -> None:
        """Initialize quick ack generator.

        Args:
            cache_dir: Directory containing cached audio files.
        """
        self._cache_dir = Path(cache_dir)
        self._patterns = [re.compile(p, re.IGNORECASE) for p in COMPLEX_PATTERNS]

    @property
    def cache_dir(self) -> Path:
        """Return cache directory."""
        return self._cache_dir

    def should_ack(self, text: str) -> bool:
        """Check if query warrants quick acknowledgment.

        Args:
            text: User query text.

        Returns:
            True if any complexity pattern matches.
        """
        return any(p.search(text) for p in self._patterns)

    def get_ack(self, language: str) -> tuple[str, Path]:
        """Get acknowledgment phrase and audio path.

        Args:
            language: Language code.

        Returns:
            Tuple of (phrase, audio_path).
        """
        phrases = ACK_PHRASES.get(language, ACK_PHRASES["en"])
        phrase = random.choice(phrases)

        # Build filename: ack_en_right.wav
        filename = f"ack_{language}_{phrase.lower()}.wav"
        audio_path = self._cache_dir / filename

        return phrase, audio_path

    def get_ack_text(self, language: str) -> str:
        """Get acknowledgment phrase text only.

        Args:
            language: Language code.

        Returns:
            Acknowledgment phrase.
        """
        phrases = ACK_PHRASES.get(language, ACK_PHRASES["en"])
        return random.choice(phrases)

    def get_phrases(self, language: str) -> list[str]:
        """Get available ack phrases for a language.

        Args:
            language: Language code.

        Returns:
            List of phrase strings.
        """
        return ACK_PHRASES.get(language, ACK_PHRASES["en"])

    def has_cached_audio(self, language: str) -> bool:
        """Check if cached audio exists for language.

        Args:
            language: Language code.

        Returns:
            True if at least one cached file exists.
        """
        phrases = ACK_PHRASES.get(language, ACK_PHRASES["en"])
        for phrase in phrases:
            filename = f"ack_{language}_{phrase.lower()}.wav"
            if (self._cache_dir / filename).exists():
                return True
        return False
