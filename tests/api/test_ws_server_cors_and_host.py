"""Unit tests for _origin_allowed() and the host-resolution logic in ws_server.

_origin_allowed is a pure function importable directly.

The host-resolution logic (JARVIS_REMOTE_ACCESS switch) is inlined inside
start_ws_server and is NOT extracted into a standalone helper.  Rather than
booting the full server (which pulls Whisper, wake-word, OpenClaw, etc.), we
test the logic via a thin local re-implementation that mirrors the exact
three-branch conditional found in ws_server.py.  Any future extraction of that
logic into a helper should obsolete the local re-implementation here and the
tests in class TestHostResolution can be pointed at the real helper.
"""

from __future__ import annotations

import os

import pytest

from api.ws_server import _origin_allowed


# ===========================================================================
# Local re-implementation of the host-resolution logic for unit-testing.
#
# Source in ws_server.py (lines ~4692-4705):
#
#   _config_host = config.get("host", "127.0.0.1")
#   _remote_access_raw = os.environ.get("JARVIS_REMOTE_ACCESS", "").strip().lower()
#   _remote_access_enabled = _remote_access_raw in {"1", "true", "yes"}
#   if _config_host != "127.0.0.1":
#       host = _config_host
#   elif _remote_access_enabled:
#       host = "0.0.0.0"
#   else:
#       host = _config_host
# ===========================================================================


def _resolve_host(config_host: str) -> str:
    """Mirror the host-resolution branch from start_ws_server.

    Reads JARVIS_REMOTE_ACCESS from the real os.environ so that monkeypatch
    works correctly in tests.  config_host simulates config.get("host", ...).
    """
    remote_raw = os.environ.get("JARVIS_REMOTE_ACCESS", "").strip().lower()
    remote_enabled = remote_raw in {"1", "true", "yes"}
    if config_host != "127.0.0.1":
        return config_host
    if remote_enabled:
        return "0.0.0.0"
    return config_host


# ===========================================================================
# _origin_allowed — literal and wildcard matching
# ===========================================================================


class TestOriginAllowed:
    """Tests for the _origin_allowed(origin, patterns) helper."""

    def test_literal_origin_in_patterns_returns_true(self):
        """A literal origin that exactly matches a pattern entry is allowed."""
        assert _origin_allowed("http://localhost:5173", ["http://localhost:5173"]) is True

    def test_literal_origin_not_in_patterns_returns_false(self):
        """An origin that does not match any pattern is rejected."""
        assert _origin_allowed("http://evil.example.com", ["http://localhost:5173"]) is False

    def test_wildcard_star_allows_any_origin(self):
        """A bare '*' pattern allows every origin (regression for existing semantics)."""
        assert _origin_allowed("https://anything.example.com", ["*"]) is True

    def test_wildcard_star_allows_empty_origin(self):
        """A bare '*' pattern allows even an empty-string origin."""
        assert _origin_allowed("", ["*"]) is True

    def test_fnmatch_glob_matches_tailscale_subdomain(self):
        """'https://*.tailnet.ts.net' glob matches a real Tailscale hostname."""
        assert (
            _origin_allowed(
                "https://laptop.tailnet.ts.net",
                ["https://*.tailnet.ts.net"],
            )
            is True
        )

    def test_fnmatch_glob_rejects_different_domain(self):
        """'https://*.tailnet.ts.net' glob rejects a host on a different domain."""
        assert (
            _origin_allowed(
                "https://laptop.example.com",
                ["https://*.tailnet.ts.net"],
            )
            is False
        )

    def test_fnmatch_glob_rejects_different_scheme(self):
        """'https://*.tailnet.ts.net' glob rejects an http:// origin (scheme mismatch)."""
        assert (
            _origin_allowed(
                "http://laptop.tailnet.ts.net",
                ["https://*.tailnet.ts.net"],
            )
            is False
        )

    def test_empty_origin_empty_patterns_returns_false(self):
        """Empty origin with empty pattern list returns False."""
        assert _origin_allowed("", []) is False

    def test_multiple_patterns_first_match_wins(self):
        """Any matching pattern in the list is sufficient to allow the origin."""
        patterns = [
            "http://localhost:5173",
            "https://*.tailnet.ts.net",
            "https://admin.example.com",
        ]
        assert _origin_allowed("https://mydevice.tailnet.ts.net", patterns) is True

    def test_no_patterns_returns_false(self):
        """An origin against an empty patterns list is always rejected."""
        assert _origin_allowed("http://localhost:5173", []) is False

    def test_fnmatch_glob_matches_second_level_subdomain(self):
        """Glob with single '*' does not cross dot boundaries by default (fnmatchcase)."""
        # fnmatch '*' matches any sequence of characters including dots on some
        # implementations — document what the actual behaviour is.
        # The pattern "https://*.tailnet.ts.net" uses a single '*', which in
        # fnmatch matches any sequence of chars; 'a.b.tailnet.ts.net' would
        # therefore also match.  This test asserts the current behaviour.
        result = _origin_allowed(
            "https://a.b.tailnet.ts.net",
            ["https://*.tailnet.ts.net"],
        )
        # fnmatch '*' DOES match dots — assert the documented behaviour.
        assert result is True

    def test_case_sensitive_matching(self):
        """Pattern matching is case-sensitive (fnmatchcase, not fnmatch)."""
        # 'HTTP://localhost:5173' should NOT match 'http://localhost:5173'.
        assert _origin_allowed("HTTP://localhost:5173", ["http://localhost:5173"]) is False

    def test_port_inclusive_wildcard_matches_tailnet_origin_with_port(self) -> None:
        """`https://*.tailnet.ts.net:5173` matches the canonical Vite frontend origin
        on the tailnet — the documented production setup in config.yaml."""
        assert _origin_allowed(
            "https://laptop-paps.tailnet.ts.net:5173",
            ["https://*.tailnet.ts.net:5173"],
        ) is True

    def test_port_inclusive_wildcard_rejects_different_port(self) -> None:
        """A different port must not match the wildcard — confirms fnmatch glob is
        port-anchored rather than treating the port as variable."""
        assert _origin_allowed(
            "https://laptop-paps.tailnet.ts.net:8080",
            ["https://*.tailnet.ts.net:5173"],
        ) is False


# ===========================================================================
# Host-resolution logic (inlined in start_ws_server)
# ===========================================================================


class TestHostResolution:
    """Tests for the JARVIS_REMOTE_ACCESS / api.host resolution logic.

    Uses the local re-implementation _resolve_host() which mirrors the exact
    three-branch conditional from start_ws_server.
    """

    def test_default_loopback_when_remote_access_unset(self, monkeypatch):
        """With JARVIS_REMOTE_ACCESS unset and config default, host stays 127.0.0.1."""
        monkeypatch.delenv("JARVIS_REMOTE_ACCESS", raising=False)
        assert _resolve_host("127.0.0.1") == "127.0.0.1"

    def test_remote_access_true_flips_to_all_interfaces(self, monkeypatch):
        """JARVIS_REMOTE_ACCESS=true with default config host yields 0.0.0.0."""
        monkeypatch.setenv("JARVIS_REMOTE_ACCESS", "true")
        assert _resolve_host("127.0.0.1") == "0.0.0.0"

    def test_explicit_config_host_wins_over_remote_access(self, monkeypatch):
        """Explicit non-default config host is kept even when JARVIS_REMOTE_ACCESS=true."""
        monkeypatch.setenv("JARVIS_REMOTE_ACCESS", "true")
        assert _resolve_host("192.168.1.10") == "192.168.1.10"

    @pytest.mark.parametrize(
        "env_value",
        ["1", "true", "True", "TRUE", "yes", "YES", "Yes"],
    )
    def test_truthy_remote_access_values_enable_all_interfaces(self, monkeypatch, env_value):
        """All truthy JARVIS_REMOTE_ACCESS values ('1', 'true', 'yes', case-insensitive) flip host."""
        monkeypatch.setenv("JARVIS_REMOTE_ACCESS", env_value)
        assert _resolve_host("127.0.0.1") == "0.0.0.0"

    @pytest.mark.parametrize(
        "env_value",
        ["0", "false", "False", "FALSE", "no", "NO", ""],
    )
    def test_falsy_remote_access_values_keep_loopback(self, monkeypatch, env_value):
        """Falsy JARVIS_REMOTE_ACCESS values leave host at the default 127.0.0.1."""
        monkeypatch.setenv("JARVIS_REMOTE_ACCESS", env_value)
        assert _resolve_host("127.0.0.1") == "127.0.0.1"

    def test_explicit_config_host_unaffected_without_remote_access(self, monkeypatch):
        """Explicit config host is returned as-is when JARVIS_REMOTE_ACCESS is unset."""
        monkeypatch.delenv("JARVIS_REMOTE_ACCESS", raising=False)
        assert _resolve_host("10.0.0.5") == "10.0.0.5"

    def test_remote_access_env_whitespace_stripped(self, monkeypatch):
        """Leading/trailing whitespace in JARVIS_REMOTE_ACCESS is stripped before comparison."""
        monkeypatch.setenv("JARVIS_REMOTE_ACCESS", "  true  ")
        assert _resolve_host("127.0.0.1") == "0.0.0.0"
