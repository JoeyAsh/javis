"""Salutation selection for JARVIS persona.

Provides runtime selection of salutation ("Sir" vs "Johannes") per voice
interaction. This stays JARVIS-native even with OpenClaw persona handling,
as it requires per-interaction randomization.

Example usage:
    from brain.salutation import get_salutation

    config = {
        "salutation_mode": "random",
        "salutation_pool": ["Sir", "Johannes"],
        "salutation_weights": [0.5, 0.5],
    }

    salutation = get_salutation(config)
    # Returns either "Sir" or "Johannes" with 50/50 probability
"""

from __future__ import annotations

import random
from typing import Any

from utils.logger import get_logger

logger = get_logger("salutation")


def get_salutation(config: dict[str, Any], seed: int | None = None) -> str:
    """Select salutation for current interaction.

    Selection happens once per voice interaction (not per-turn).
    Supports fixed mode (always use first in pool) or random mode
    (weighted random selection from pool).

    Args:
        config: Persona config section containing:
            - salutation_mode: "random" or "fixed"
            - salutation_pool: List of salutation options
            - salutation_weights: List of weights (must sum to ~1.0)
            - salutation_override: Optional forced salutation
            - salutation_seed: Optional seed for reproducibility
        seed: Optional seed override for reproducibility in tests.

    Returns:
        Selected salutation string.

    Examples:
        >>> get_salutation({"salutation_mode": "fixed", "salutation_pool": ["Sir"]})
        'Sir'

        >>> # With seed for reproducibility
        >>> get_salutation({"salutation_pool": ["Sir", "Johannes"]}, seed=42)
        'Sir'  # or 'Johannes' - deterministic based on seed
    """
    # Check for override
    override = config.get("salutation_override")
    if override:
        return override

    # Get pool and weights
    pool = config.get("salutation_pool", ["Sir", "Johannes"])
    weights = config.get("salutation_weights", [0.5, 0.5])

    # Validate pool
    if not pool:
        logger.warning("Empty salutation pool, defaulting to 'Sir'")
        return "Sir"

    # Fixed mode: always use first in pool
    mode = config.get("salutation_mode", "random")
    if mode == "fixed":
        return pool[0]

    # Random mode with optional seed
    effective_seed = seed if seed is not None else config.get("salutation_seed")
    if effective_seed is not None:
        random.seed(effective_seed)

    # Ensure weights match pool size
    if len(weights) != len(pool):
        logger.warning(
            f"Salutation weights ({len(weights)}) don't match pool ({len(pool)}), "
            "using equal weights"
        )
        weights = [1.0 / len(pool)] * len(pool)

    selected = random.choices(pool, weights=weights, k=1)[0]
    logger.debug(f"Selected salutation: {selected}")

    return selected


def get_salutation_for_language(
    base_salutation: str,
    language: str,
    formal: bool = True,
) -> str:
    """Adjust salutation for language context.

    For most cases, "Sir" is preserved across languages as it sounds
    sophisticated in German context. This function allows for future
    language-specific adjustments if needed.

    Args:
        base_salutation: The base salutation (e.g., "Sir", "Johannes").
        language: Language code (e.g., "en", "de").
        formal: Whether to use formal register.

    Returns:
        Adjusted salutation string.
    """
    # Currently, "Sir" is preserved in all languages
    # This function exists for future expansion
    return base_salutation
