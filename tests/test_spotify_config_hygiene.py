"""Backend hygiene meta-test — config/config.yaml Spotify scopes.

Verifies that the three new scopes required by issue #58 are present in
the spotify.scopes list in config/config.yaml.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

REQUIRED_SCOPES = {
    "playlist-read-private",
    "playlist-read-collaborative",
    "user-library-read",
}


def _load_config() -> dict:
    """Load config/config.yaml relative to the project root."""
    repo_root = Path(__file__).parent.parent
    config_path = repo_root / "config" / "config.yaml"
    with open(config_path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def test_spotify_scopes_include_required_library_scopes():
    """config.yaml spotify.scopes must include all three issue-#58 scopes."""
    config = _load_config()
    scopes: list[str] = config.get("spotify", {}).get("scopes", [])
    scope_set = set(scopes)

    missing = REQUIRED_SCOPES - scope_set
    assert not missing, (
        f"Missing required Spotify scopes in config/config.yaml: {missing!r}. "
        f"Current scopes: {scopes!r}"
    )


def test_spotify_enabled_in_config():
    """config.yaml spotify.enabled must be true."""
    config = _load_config()
    assert config.get("spotify", {}).get("enabled") is True
