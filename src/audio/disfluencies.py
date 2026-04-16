"""Disfluency injection for natural speech (opt-in).

Adds natural speech imperfections like "um", "well" at the start
of responses to make JARVIS sound more human-like.

Default: OFF (may sound off-brand for JARVIS persona)

Example usage:
    from audio.disfluencies import DisfluencyInjector

    injector = DisfluencyInjector(config["voice"])

    # Maybe add a disfluency to the response
    text = injector.maybe_inject("I'll check that for you.", "en")
    # Might return: "Well, I'll check that for you."
"""

from __future__ import annotations

import random
from typing import Any

from utils.logger import get_logger

logger = get_logger("disfluencies")

# Default disfluency phrases by language
DEFAULT_DISFLUENCY_PHRASES = {
    "de": ["also", "nun"],
    "en": ["well", "so"],
}


class DisfluencyInjector:
    """Inject natural disfluencies into responses.

    Opt-in feature that prepends occasional speech imperfections
    to make responses sound more natural.

    Attributes:
        enabled: Whether injection is enabled.
        rate: Probability of injection per response.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize disfluency injector.

        Args:
            config: Voice config section containing:
                - natural_disfluencies: bool (default: False)
                - disfluency_rate: float 0-1 (default: 0.1)
                - disfluency_phrases: dict by language
        """
        self._enabled = config.get("natural_disfluencies", False)
        self._rate = config.get("disfluency_rate", 0.1)
        self._phrases = config.get("disfluency_phrases", DEFAULT_DISFLUENCY_PHRASES)

    @property
    def enabled(self) -> bool:
        """Check if disfluencies are enabled."""
        return self._enabled

    @property
    def rate(self) -> float:
        """Get injection rate."""
        return self._rate

    def maybe_inject(self, text: str, language: str) -> str:
        """Maybe inject a disfluency at the start of response.

        Injection happens with probability `rate` when enabled.

        Args:
            text: Original response text.
            language: Language code.

        Returns:
            Text with possible disfluency prepended.
        """
        if not self._enabled:
            return text

        if random.random() > self._rate:
            return text

        phrases = self._phrases.get(language, self._phrases.get("en", []))
        if not phrases:
            return text

        disfluency = random.choice(phrases)
        logger.debug(f"Injecting disfluency: {disfluency}")

        # Capitalize the original text properly after disfluency
        if text and text[0].isupper():
            text = text[0].lower() + text[1:]

        return f"{disfluency.capitalize()}, {text}"

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable disfluency injection.

        Args:
            enabled: Whether to enable.
        """
        self._enabled = enabled

    def set_rate(self, rate: float) -> None:
        """Set injection rate.

        Args:
            rate: Probability 0-1.
        """
        self._rate = max(0.0, min(1.0, rate))

    def get_phrases(self, language: str) -> list[str]:
        """Get disfluency phrases for a language.

        Args:
            language: Language code.

        Returns:
            List of phrase strings.
        """
        return self._phrases.get(language, self._phrases.get("en", []))
