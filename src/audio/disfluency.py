"""Opt-in disfluency prepending for natural TTS speech.

When ``voice.disfluencies_enabled`` is true, JARVIS randomly prepends a
short disfluency token (e.g. "äh,", "moment,") before the first TTS
sentence of an LLM response.  Keeps JARVIS sounding human without the
overhead of full prosody manipulation.

Example:
    from audio.disfluency import maybe_prepend_disfluency

    text = maybe_prepend_disfluency("Die Antwort lautet 42.", "de", enabled=True)
    # → "Äh, die Antwort lautet 42."  (with 20% probability)
"""

from __future__ import annotations

import random

from utils.logger import get_logger

logger = get_logger("disfluency")

# Default phrase pools, keyed by ISO-639-1 language code.
_POOLS: dict[str, list[str]] = {
    "de": ["äh,", "mhm,", "moment,"],
    "en": ["uh,", "um,", "well,"],
}


def maybe_prepend_disfluency(
    text: str,
    language: str,
    enabled: bool,
    probability: float = 0.20,
) -> str:
    """Maybe prepend a single disfluency token to *text*.

    Args:
        text: The LLM response text that will be passed to TTS.
        language: ISO-639-1 language code (e.g. ``"de"``, ``"en"``).
        enabled: Master gate — when ``False`` the function is a no-op.
        probability: Probability (0–1) that a disfluency is prepended.
            Defaults to 0.20 (20 %).

    Returns:
        Original text unchanged when disabled or the random draw misses;
        otherwise the disfluency prepended with a space and the first
        character of *text* lowercased so the sentence still reads naturally.
    """
    if not enabled:
        return text

    if not text:
        return text

    if random.random() >= probability:
        return text

    pool = _POOLS.get(language) or _POOLS.get("de", [])
    if not pool:
        return text

    token = random.choice(pool)

    # Lower-case the first letter of the original text so the disfluency
    # reads as a sentence-initial tag rather than a disconnected fragment.
    head = text[0].lower() + text[1:] if len(text) > 1 else text.lower()
    # Capitalise the disfluency token so the combined text starts properly.
    result = f"{token.capitalize()} {head}"
    logger.debug(f"Disfluency prepended ({language}): {token!r}")
    return result
