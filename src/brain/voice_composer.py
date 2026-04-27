"""Voice Composer — unified TTS text post-processing for JARVIS.

Consolidates all voice-channel output formatting: markdown stripping,
per-sentence length capping, salutation insertion (deterministic "Sir"
per Decision 1 of 2026-04-27), and whitespace normalisation.

Provides a stub ``mood_snapshot`` parameter for Phase 3 integration.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any

from audio.fish_tts import strip_markdown_for_tts
from utils.config_loader import get_config
from utils.logger import get_logger

logger = get_logger("voice_composer")


@dataclass
class ComposeResult:
    """Result of a VoiceComposer.compose() call."""

    text: str
    """Final composed plain-text string (all sentences joined by space)."""

    salutation_used: str | None
    """Salutation prepended to the first sentence, or None if not prepended."""

    sentences: list[str] = field(default_factory=list)
    """Individual sentences after splitting/truncation."""

    clipped: bool = False
    """True when any sentence was truncated due to max_sentence_words."""


# ---------------------------------------------------------------------------
# Sentence splitting helpers
# ---------------------------------------------------------------------------

# Matches sentence-ending punctuation followed by whitespace or end-of-string.
_SENTENCE_END_RE = re.compile(r"(?<=[.!?…])\s+")


def _split_into_sentences(text: str) -> list[str]:
    """Split text into sentences on .!?… boundaries.

    Args:
        text: Normalised plain text.

    Returns:
        Non-empty sentence strings.
    """
    raw = _SENTENCE_END_RE.split(text.strip())
    return [s.strip() for s in raw if s.strip()]


def _cap_sentence(
    sentence: str,
    max_words: int,
    mode: str,
) -> tuple[list[str], bool]:
    """Apply per-sentence word cap.

    Args:
        sentence: A single sentence string.
        max_words: Maximum words per output sentence.
        mode: ``"split"`` to break into multiple sentences, ``"truncate"``
            to cut with ``…``.

    Returns:
        Tuple of (output_sentence_list, clipped).
        ``clipped`` is True only when mode is ``"truncate"`` and the
        sentence was actually shortened.
    """
    words = sentence.split()
    if len(words) <= max_words:
        return [sentence], False

    if mode == "truncate":
        truncated = " ".join(words[:max_words]) + "…"
        return [truncated], True

    # split mode: break into chunks of max_words words.
    chunks: list[str] = []
    for start in range(0, len(words), max_words):
        chunk = " ".join(words[start : start + max_words])
        chunks.append(chunk)
    return chunks, False


class VoiceComposer:
    """Formats LLM output text for TTS consumption.

    Single public entry point: :meth:`compose`.  Injected with config at
    construction time for testability — no module-level singletons.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialise VoiceComposer with optional config override.

        Args:
            config: The ``voice_composer`` config section.  When ``None``
                the section is loaded from the global config at first use.
        """
        if config is None:
            cfg = get_config()
            config = cfg.get_section("voice_composer") or {}
        self._max_sentence_words: int = int(config.get("max_sentence_words", 50))
        self._long_sentence_mode: str = str(config.get("long_sentence_mode", "split"))
        # salutation_policy is always "sir_only" in V1 per Decision 1.
        self._salutation_policy: str = str(config.get("salutation_policy", "sir_only"))

        # Track last compose call for brain_inspector broadcasts.
        self._last_compose_ts: str | None = None
        self._last_salutation: str | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compose(
        self,
        text: str,
        language: str,
        mood_snapshot: Any | None = None,  # Phase 3 stub — ignored for now
    ) -> ComposeResult:
        """Format LLM output text for TTS.

        Steps:
        1. Strip markdown and filler phrases via ``strip_markdown_for_tts``.
        2. Normalise whitespace.
        3. Split into sentences.
        4. Apply per-sentence word cap (split or truncate).
        5. Insert salutation at the front of the first sentence.
        6. Join all sentences, update internal state.

        Args:
            text: Raw LLM reply text (may contain markdown).
            language: BCP-47 language code (e.g. ``"de"``, ``"en"``).
            mood_snapshot: Reserved for Phase 3 mood signals — ignored.

        Returns:
            :class:`ComposeResult` with composed text, individual sentences,
            salutation used, and clipped flag.
        """
        if not text or not text.strip():
            return ComposeResult(text="", salutation_used=None, sentences=[], clipped=False)

        # Step 1: markdown stripping.
        clean = strip_markdown_for_tts(text)

        # Step 2: whitespace normalisation.
        clean = re.sub(r"\s{2,}", " ", clean).strip()

        if not clean:
            return ComposeResult(text="", salutation_used=None, sentences=[], clipped=False)

        # Step 3: split into sentences.
        raw_sentences = _split_into_sentences(clean)
        if not raw_sentences:
            raw_sentences = [clean]

        # Step 4: per-sentence word cap.
        capped_sentences: list[str] = []
        any_clipped = False
        for sentence in raw_sentences:
            parts, clipped = _cap_sentence(sentence, self._max_sentence_words, self._long_sentence_mode)
            capped_sentences.extend(parts)
            if clipped:
                any_clipped = True

        # Step 5: salutation insertion (Decision 1 — always "Sir").
        salutation_used: str | None = None
        if capped_sentences:
            salutation = self._get_salutation()
            salutation_used = salutation
            if salutation:
                capped_sentences[0] = f"{salutation}, {capped_sentences[0]}"

        # Step 6: compose final text.
        final_text = " ".join(capped_sentences)

        # Update inspector state.
        self._last_compose_ts = _iso_now()
        self._last_salutation = salutation_used

        logger.debug(
            f"VoiceComposer.compose: {len(raw_sentences)} raw sentence(s) → "
            f"{len(capped_sentences)} output sentence(s), clipped={any_clipped}"
        )

        return ComposeResult(
            text=final_text,
            salutation_used=salutation_used,
            sentences=capped_sentences,
            clipped=any_clipped,
        )

    def get_salutation(self) -> str:
        """Return the salutation string (always 'Sir' in V1).

        Returns:
            Salutation string.
        """
        return self._get_salutation()

    def status_snapshot(self) -> dict[str, Any]:
        """Return a dict suitable for the brain_inspector WS payload.

        Returns:
            Dict with ``last_compose_ts`` and ``last_salutation``.
        """
        return {
            "last_compose_ts": self._last_compose_ts,
            "last_salutation": self._last_salutation,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_salutation(self) -> str:
        """Return the salutation per configured policy.

        Decision 1: always "Sir" regardless of ``salutation_policy`` value.
        """
        return "Sir"


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def _iso_now() -> str:
    """Return current UTC time as ISO-8601 string."""
    import datetime

    return datetime.datetime.now(datetime.timezone.utc).isoformat()
