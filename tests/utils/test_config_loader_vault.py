"""Tests for vault.path expansion + env override in src/utils/config_loader.py.

Covers:
- vault.path with leading '~' is expanded to absolute home path on load.
- JARVIS_VAULT_PATH env-var overrides YAML value AND is '~'-expanded.
- Empty/missing vault block does not crash; vault.enabled defaults sensibly.
- JARVIS_VAULT_PATH with a plain absolute path (no '~') is preserved as-is.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fresh_loader(config_dict: dict[str, Any]) -> "ConfigLoader":
    """Return a ConfigLoader whose _config was built from config_dict.

    Bypasses file I/O by monkeypatching _load() to directly populate
    the private _config, then calling _apply_env_overrides() explicitly
    so env-var logic runs.
    """
    from utils.config_loader import ConfigLoader

    # Reset the singleton so each test gets a fresh instance.
    ConfigLoader._instance = None
    ConfigLoader._config = {}

    loader = ConfigLoader.__new__(ConfigLoader)
    loader._config = dict(config_dict)
    loader._apply_env_overrides()
    return loader


# ---------------------------------------------------------------------------
# vault.path ~ expansion from YAML
# ---------------------------------------------------------------------------


class TestVaultPathTildeExpansion:
    """vault.path with leading '~' expands to an absolute path on load."""

    def test_tilde_in_yaml_vault_path_is_expanded(self):
        """ConfigLoader expands '~/Obsidian/jarvis-vault' to an absolute path."""
        raw_config = {
            "vault": {
                "enabled": True,
                "path": "~/Obsidian/jarvis-vault",
            }
        }

        # Ensure JARVIS_VAULT_PATH env var is NOT set.
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("JARVIS_VAULT_PATH", None)
            loader = _fresh_loader(raw_config)

        vault_path = loader.get_section("vault").get("path", "")
        assert vault_path != "~/Obsidian/jarvis-vault", "~ should have been expanded"
        assert os.path.isabs(vault_path), f"Path should be absolute: {vault_path!r}"
        assert "Obsidian" in vault_path or "jarvis-vault" in vault_path

    def test_absolute_path_in_yaml_unchanged(self):
        """An already-absolute path in YAML is left unchanged."""
        raw_config = {
            "vault": {
                "enabled": True,
                "path": "/srv/jarvis-vault",
            }
        }

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("JARVIS_VAULT_PATH", None)
            loader = _fresh_loader(raw_config)

        vault_path = loader.get_section("vault").get("path", "")
        assert vault_path == "/srv/jarvis-vault"

    def test_empty_path_does_not_crash(self):
        """An empty vault.path in YAML does not raise any exception."""
        raw_config = {
            "vault": {
                "enabled": True,
                "path": "",
            }
        }

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("JARVIS_VAULT_PATH", None)
            loader = _fresh_loader(raw_config)  # must not raise


# ---------------------------------------------------------------------------
# JARVIS_VAULT_PATH env-var override
# ---------------------------------------------------------------------------


class TestVaultPathEnvOverride:
    """JARVIS_VAULT_PATH env-var overrides the YAML value."""

    def test_env_var_overrides_yaml_value(self):
        """JARVIS_VAULT_PATH=/tmp/test-vault overrides YAML vault.path."""
        raw_config = {
            "vault": {
                "enabled": True,
                "path": "~/Obsidian/jarvis-vault",
            }
        }

        with patch.dict(os.environ, {"JARVIS_VAULT_PATH": "/tmp/test-vault"}, clear=False):
            loader = _fresh_loader(raw_config)

        vault_path = loader.get_section("vault").get("path", "")
        assert vault_path == "/tmp/test-vault"

    def test_env_var_with_tilde_is_expanded(self):
        """JARVIS_VAULT_PATH=~/custom-vault → ~ is also expanded."""
        raw_config = {
            "vault": {
                "enabled": True,
                "path": "~/Obsidian/jarvis-vault",
            }
        }

        with patch.dict(os.environ, {"JARVIS_VAULT_PATH": "~/custom-vault"}, clear=False):
            loader = _fresh_loader(raw_config)

        vault_path = loader.get_section("vault").get("path", "")
        assert not vault_path.startswith("~"), f"~ was not expanded: {vault_path!r}"
        assert os.path.isabs(vault_path), f"Path should be absolute: {vault_path!r}"
        assert "custom-vault" in vault_path

    def test_env_var_overrides_even_when_no_vault_yaml_block(self):
        """JARVIS_VAULT_PATH creates vault section even if YAML had none."""
        raw_config: dict[str, Any] = {}  # no vault block at all

        with patch.dict(os.environ, {"JARVIS_VAULT_PATH": "/tmp/test-vault"}, clear=False):
            loader = _fresh_loader(raw_config)

        vault_path = loader.get_section("vault").get("path", "")
        assert vault_path == "/tmp/test-vault"

    def test_env_var_absolute_path_preserved_without_expansion(self):
        """An absolute JARVIS_VAULT_PATH (no ~) is stored as-is."""
        raw_config: dict[str, Any] = {"vault": {"path": "~/default"}}

        with patch.dict(os.environ, {"JARVIS_VAULT_PATH": "/absolute/path"}, clear=False):
            loader = _fresh_loader(raw_config)

        vault_path = loader.get_section("vault").get("path", "")
        assert vault_path == "/absolute/path"


# ---------------------------------------------------------------------------
# Empty / missing vault block
# ---------------------------------------------------------------------------


class TestVaultBlockAbsent:
    """Missing or empty vault block does not crash and defaults are sensible."""

    def test_no_vault_block_does_not_crash(self):
        """ConfigLoader with no vault block at all does not raise."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("JARVIS_VAULT_PATH", None)
            loader = _fresh_loader({})  # must not raise

        # vault section should be empty or missing, not an error.
        vault = loader.get_section("vault")
        assert isinstance(vault, dict)

    def test_vault_enabled_defaults_sensibly_when_absent(self):
        """When vault block is absent, enabled check with default=False returns False."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("JARVIS_VAULT_PATH", None)
            loader = _fresh_loader({})

        # Caller uses vault_cfg.get("enabled", False) → should be falsy.
        vault_cfg = loader.get_section("vault") or {}
        assert not vault_cfg.get("enabled", False)

    def test_empty_vault_block_does_not_crash(self):
        """An empty vault dict in YAML does not raise."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("JARVIS_VAULT_PATH", None)
            loader = _fresh_loader({"vault": {}})  # must not raise

    def test_vault_block_with_only_enabled_flag_does_not_crash(self):
        """vault: {enabled: true} with no path does not raise."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("JARVIS_VAULT_PATH", None)
            loader = _fresh_loader({"vault": {"enabled": True}})  # must not raise

        vault_cfg = loader.get_section("vault")
        assert vault_cfg.get("enabled") is True


# ---------------------------------------------------------------------------
# ConfigLoader.get() dot-notation for vault keys
# ---------------------------------------------------------------------------


class TestVaultConfigGet:
    """ConfigLoader.get() with dot-notation reaches vault sub-keys."""

    def test_get_vault_path_via_dot_notation(self):
        """get('vault.path') returns the expanded vault path."""
        raw_config = {
            "vault": {
                "path": "~/Obsidian/jarvis-vault",
                "enabled": True,
            }
        }

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("JARVIS_VAULT_PATH", None)
            loader = _fresh_loader(raw_config)

        path_via_dot = loader.get("vault.path", "")
        assert path_via_dot != "~/Obsidian/jarvis-vault"
        assert os.path.isabs(path_via_dot)

    def test_get_vault_enabled_via_dot_notation(self):
        """get('vault.enabled') returns the enabled flag."""
        raw_config = {"vault": {"enabled": True, "path": "/some/path"}}

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("JARVIS_VAULT_PATH", None)
            loader = _fresh_loader(raw_config)

        assert loader.get("vault.enabled") is True
