"""Conversation-mode helpers for JARVIS voice interaction.

Keeps the mic "open" for a short follow-up window after every reply so
the user can continue talking without repeating the wake word, and ends
the session cleanly on natural sleep phrases like "danke" / "thanks".

Usage
-----

    cm = ConversationMode(config["voice"]["conversation_mode"])
    # After a voice turn completes:
    cm.begin_window()
    # At the next audio frame:
    if cm.in_window():
        # route straight into LISTENING, skip wake word
        ...
    # At start of pipeline, after STT:
    if cm.detect_sleep_phrase(text, lang):
        reply = cm.closing_phrase(lang, salutation="Johannes")
        cm.end_window()
        # speak `reply`, then return to idle
"""

from __future__ import annotations

import random
import re
import time
from dataclasses import dataclass, field
from typing import Any

from utils.logger import get_logger

logger = get_logger("conversation_mode")

_TOKEN_SEP = re.compile(r"[\s,\.\!\?\-—;:]+")


def _tokenize(text: str) -> list[str]:
    """Split *text* on whitespace and punctuation, dropping empty strings."""
    return [t for t in _TOKEN_SEP.split(text) if t]


_DEFAULT_SLEEP_PHRASES: dict[str, list[str]] = {
    "de": [
        "danke",
        "dankeschön",
        "das war's",
        "das wars",
        "passt so",
        "passt",
        "bis später",
        "bis bald",
        "tschüss",
        "tschau",
        "ciao",
        "alles gut",
        "das reicht",
        "reicht so",
        "nichts mehr",
        "schönen tag noch",
    ],
    "en": [
        "thanks",
        "thank you",
        "that's all",
        "that's it",
        "bye",
        "goodbye",
        "see you",
        "later",
        "we're done",
        "nothing else",
        "all good",
        "that'll do",
    ],
}

_DEFAULT_CLOSING_PHRASES: dict[str, list[str]] = {
    "de": [
        "Gern, {sal}.",
        "Jederzeit, {sal}.",
        "Immer wieder, {sal}.",
        "Gern geschehen, {sal}.",
    ],
    "en": [
        "Anytime, {sal}.",
        "Always, {sal}.",
        "At your service, {sal}.",
        "My pleasure, {sal}.",
    ],
}

_DEFAULT_WINDOW_SECONDS = 18.0


@dataclass
class ConversationMode:
    """Per-connection follow-up window + sleep-phrase detection.

    The window counter is driven by wall-clock time so concurrent audio
    frames see a consistent "in window" answer without us having to
    reschedule timers.
    """

    window_seconds: float = _DEFAULT_WINDOW_SECONDS
    enabled: bool = True
    sleep_phrases: dict[str, list[str]] = field(
        default_factory=lambda: {k: list(v) for k, v in _DEFAULT_SLEEP_PHRASES.items()}
    )
    closing_phrases: dict[str, list[str]] = field(
        default_factory=lambda: {
            k: list(v) for k, v in _DEFAULT_CLOSING_PHRASES.items()
        }
    )
    _follow_up_until: float = field(default=0.0, init=False)

    @classmethod
    def from_config(cls, cfg: dict[str, Any] | None) -> ConversationMode:
        """Build from a ``voice.conversation_mode`` config dict.

        Accepts a ``None`` / missing config and falls back to defaults.
        Unknown keys are ignored; sleep and closing phrase maps are
        merged (config overrides default language lists if present).
        """
        if not cfg:
            return cls()

        sleep = {k: list(v) for k, v in _DEFAULT_SLEEP_PHRASES.items()}
        for lang, phrases in (cfg.get("sleep_phrases") or {}).items():
            if isinstance(phrases, list):
                sleep[lang] = [str(p) for p in phrases]

        closing = {k: list(v) for k, v in _DEFAULT_CLOSING_PHRASES.items()}
        for lang, phrases in (cfg.get("closing_phrases") or {}).items():
            if isinstance(phrases, list):
                closing[lang] = [str(p) for p in phrases]

        return cls(
            window_seconds=float(
                cfg.get("follow_up_window_seconds", _DEFAULT_WINDOW_SECONDS)
            ),
            enabled=bool(cfg.get("enabled", True)),
            sleep_phrases=sleep,
            closing_phrases=closing,
        )

    # ------------------------------------------------------------------ window

    def begin_window(self) -> None:
        """Arm the follow-up window: wake-word check skipped for N s."""
        if not self.enabled:
            return
        self._follow_up_until = time.time() + self.window_seconds
        logger.debug(f"Follow-up window armed for {self.window_seconds:.1f}s")

    def end_window(self) -> None:
        """Close the window immediately (e.g. on sleep phrase)."""
        self._follow_up_until = 0.0

    def in_window(self) -> bool:
        """``True`` iff the follow-up window is still active."""
        return self.enabled and time.time() < self._follow_up_until

    def seconds_remaining(self) -> float:
        """Seconds left in the current window, clamped to ``>= 0``."""
        return max(0.0, self._follow_up_until - time.time())

    # ----------------------------------------------------------- sleep phrases

    def detect_sleep_phrase(self, text: str, language: str) -> bool:
        """Return ``True`` iff the user's spoken text signals "we're done".

        A phrase matches only when at least one of three conditions holds:

        1. The normalised utterance is exactly the phrase (standalone).
        2. The normalised utterance contains ≤ 4 tokens AND the phrase
           appears in it at a word boundary.
        3. The phrase appears at the very end of the utterance (terminal
           position) at a word boundary.

        This prevents mid-sentence occurrences such as
        ``"Danke für die Info, kannst du noch das Licht anmachen?"``
        from falsely closing the session.  ``dankbar`` still does not
        match ``danke`` because all branches use word-boundary anchors.
        """
        if not text:
            return False

        lang = language.lower() if language else "de"
        phrases = self.sleep_phrases.get(lang)
        if phrases is None:
            # Fallback: try both DE and EN.
            phrases = self.sleep_phrases.get("de", []) + self.sleep_phrases.get(
                "en", []
            )

        normalised = text.lower().strip().rstrip(".!?,;—-")
        tokens = _tokenize(normalised)

        for phrase in phrases:
            p = phrase.lower().strip()
            if not p:
                continue

            # Branch 1: exact match after normalisation.
            if normalised == p:
                return True

            pattern = r"\b" + re.escape(p) + r"\b"

            # Branch 2: short utterance (≤ 4 tokens) containing the phrase.
            if len(tokens) <= 4 and re.search(pattern, normalised):
                return True

            # Branch 3: phrase is terminal — utterance ends with the phrase.
            end_pattern = pattern + r"\s*$"
            if re.search(end_pattern, normalised):
                return True

        return False

    # ---------------------------------------------------------- closing phrase

    def closing_phrase(self, language: str, salutation: str) -> str:
        """Return a randomised closing line with the salutation filled in."""
        lang = language.lower() if language else "de"
        pool = self.closing_phrases.get(lang) or self.closing_phrases.get("de", [])
        if not pool:
            return ""
        template = random.choice(pool)
        return template.format(sal=salutation)
