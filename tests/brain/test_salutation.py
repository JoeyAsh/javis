"""Unit tests for salutation selection.

Tests cover:
- Fixed mode selection
- Random mode with weights
- Override handling
- Seed for reproducibility
"""

import pytest

from brain.salutation import get_salutation, get_salutation_for_language


class TestGetSalutation:
    """Tests for get_salutation function."""

    def test_fixed_mode_returns_first(self):
        """Test that fixed mode returns first in pool."""
        config = {
            "salutation_mode": "fixed",
            "salutation_pool": ["Sir", "Johannes"],
        }

        result = get_salutation(config)

        assert result == "Sir"

    def test_fixed_mode_single_option(self):
        """Test fixed mode with single option."""
        config = {
            "salutation_mode": "fixed",
            "salutation_pool": ["Johannes"],
        }

        result = get_salutation(config)

        assert result == "Johannes"

    def test_override_takes_precedence(self):
        """Test that override takes precedence over pool."""
        config = {
            "salutation_mode": "random",
            "salutation_pool": ["Sir", "Johannes"],
            "salutation_override": "Master Wayne",
        }

        result = get_salutation(config)

        assert result == "Master Wayne"

    def test_empty_pool_defaults_to_sir(self):
        """Test that empty pool defaults to 'Sir'."""
        config = {"salutation_pool": []}

        result = get_salutation(config)

        assert result == "Sir"

    def test_missing_pool_uses_defaults(self):
        """Test that missing pool uses defaults."""
        config = {"salutation_mode": "fixed"}

        result = get_salutation(config)

        assert result in ["Sir", "Johannes"]

    def test_seed_produces_consistent_results(self):
        """Test that same seed produces same result."""
        config = {
            "salutation_mode": "random",
            "salutation_pool": ["Sir", "Johannes"],
            "salutation_weights": [0.5, 0.5],
        }

        results = [get_salutation(config, seed=42) for _ in range(5)]

        # All results with same seed should be identical
        assert len(set(results)) == 1

    def test_different_seeds_can_produce_different_results(self):
        """Test that different seeds can produce different results."""
        config = {
            "salutation_mode": "random",
            "salutation_pool": ["Sir", "Johannes"],
            "salutation_weights": [0.5, 0.5],
        }

        # Try multiple seeds to find different results
        results = {get_salutation(config, seed=i) for i in range(100)}

        # With 50/50 weights, we should get both options
        assert len(results) == 2

    def test_config_seed_used_when_no_override(self):
        """Test that config seed is used when seed param not provided."""
        config = {
            "salutation_mode": "random",
            "salutation_pool": ["Sir", "Johannes"],
            "salutation_seed": 42,
        }

        result1 = get_salutation(config)
        result2 = get_salutation(config)  # Uses same config seed

        # Note: The seed is used each time, so results should match
        assert result1 == result2

    def test_weight_mismatch_uses_equal_weights(self):
        """Test that weight/pool size mismatch uses equal weights."""
        config = {
            "salutation_mode": "random",
            "salutation_pool": ["Sir", "Johannes", "Master"],
            "salutation_weights": [0.5, 0.5],  # Only 2 weights for 3 options
        }

        # Should not raise, uses equal weights
        result = get_salutation(config, seed=42)

        assert result in ["Sir", "Johannes", "Master"]

    def test_high_weight_bias(self):
        """Test that high weight produces biased results."""
        config = {
            "salutation_mode": "random",
            "salutation_pool": ["Likely", "Unlikely"],
            "salutation_weights": [0.99, 0.01],
        }

        # With many tries, "Likely" should dominate
        results = [get_salutation(config, seed=i) for i in range(100)]
        likely_count = results.count("Likely")

        assert likely_count > 90


class TestGetSalutationForLanguage:
    """Tests for get_salutation_for_language function."""

    def test_sir_preserved_in_english(self):
        """Test that Sir is preserved in English."""
        result = get_salutation_for_language("Sir", "en")

        assert result == "Sir"

    def test_sir_preserved_in_german(self):
        """Test that Sir is preserved in German."""
        result = get_salutation_for_language("Sir", "de")

        assert result == "Sir"

    def test_name_preserved_across_languages(self):
        """Test that name is preserved across languages."""
        result_en = get_salutation_for_language("Johannes", "en")
        result_de = get_salutation_for_language("Johannes", "de")

        assert result_en == "Johannes"
        assert result_de == "Johannes"
