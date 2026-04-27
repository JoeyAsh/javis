"""Unit tests for Tailscale-related helpers in utils.device.

Covers:
- resolve_tailscale_hostname(): env-var fast path, subprocess happy path,
  all exception paths, bad output paths, and result caching.
- resolve_advertise_host(): regression for existing env/config priority,
  Tailscale auto-detect integration, bind_host fallback.

All subprocess calls and env vars are mocked — no real Tailscale binary is
required or invoked.
"""

from __future__ import annotations

import json
import subprocess
from subprocess import CompletedProcess
from unittest.mock import patch

import pytest

import utils.device as device_module
from utils.device import resolve_advertise_host, resolve_tailscale_hostname


# ---------------------------------------------------------------------------
# Fixture: reset module-level cache before every test so calls are isolated
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_tailscale_cache():
    """Reset the module-level Tailscale hostname cache to its initial sentinel.

    resolve_tailscale_hostname caches its result in two module globals after
    the first call.  Without this fixture each test would see the cached result
    from the previous test and subprocess would never be called again.
    """
    device_module._tailscale_hostname_cache = None
    device_module._tailscale_hostname_resolved = False
    yield
    # Reset again after the test to avoid leaking state to the next file.
    device_module._tailscale_hostname_cache = None
    device_module._tailscale_hostname_resolved = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tailscale_stdout(dns_name: str) -> str:
    """Return a minimal tailscale status JSON blob with the given DNSName."""
    return json.dumps({"Self": {"DNSName": dns_name}})


def _completed(returncode: int = 0, stdout: str = "", stderr: str = "") -> CompletedProcess:
    """Build a mock CompletedProcess for subprocess.run."""
    return CompletedProcess(
        args=["tailscale", "status", "--json"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


# ===========================================================================
# resolve_tailscale_hostname — env-var fast path
# ===========================================================================


def test_resolve_tailscale_hostname_env_var_wins(monkeypatch):
    """When TAILSCALE_HOSTNAME is set, it is returned verbatim without calling subprocess."""
    monkeypatch.setenv("TAILSCALE_HOSTNAME", "my-laptop.tailnet.ts.net")

    with patch("subprocess.run") as mock_run:
        result = resolve_tailscale_hostname()

    assert result == "my-laptop.tailnet.ts.net"
    mock_run.assert_not_called()


def test_resolve_tailscale_hostname_env_var_whitespace_stripped(monkeypatch):
    """TAILSCALE_HOSTNAME is stripped of surrounding whitespace."""
    monkeypatch.setenv("TAILSCALE_HOSTNAME", "  device.ts.net  ")

    result = resolve_tailscale_hostname()

    assert result == "device.ts.net"


# ===========================================================================
# resolve_tailscale_hostname — subprocess happy path
# ===========================================================================


def test_resolve_tailscale_hostname_subprocess_happy_path(monkeypatch):
    """Returns DNS name from tailscale status --json with trailing dot stripped."""
    monkeypatch.delenv("TAILSCALE_HOSTNAME", raising=False)
    stdout = _make_tailscale_stdout("laptop-paps.tailnet.ts.net.")

    with patch("subprocess.run", return_value=_completed(stdout=stdout)) as mock_run:
        result = resolve_tailscale_hostname()

    assert result == "laptop-paps.tailnet.ts.net"
    mock_run.assert_called_once()


def test_resolve_tailscale_hostname_trailing_dot_stripped(monkeypatch):
    """The single trailing dot appended by Tailscale FQDN format is removed."""
    monkeypatch.delenv("TAILSCALE_HOSTNAME", raising=False)
    stdout = _make_tailscale_stdout("rpi-five.tailnet.ts.net.")

    with patch("subprocess.run", return_value=_completed(stdout=stdout)):
        result = resolve_tailscale_hostname()

    assert not result.endswith(".")
    assert result == "rpi-five.tailnet.ts.net"


# ===========================================================================
# resolve_tailscale_hostname — error / bad-output paths
# ===========================================================================


def test_resolve_tailscale_hostname_file_not_found_returns_none(monkeypatch):
    """Returns None when subprocess.run raises FileNotFoundError (CLI not installed)."""
    monkeypatch.delenv("TAILSCALE_HOSTNAME", raising=False)

    with patch("subprocess.run", side_effect=FileNotFoundError("tailscale not found")):
        result = resolve_tailscale_hostname()

    assert result is None


def test_resolve_tailscale_hostname_timeout_returns_none(monkeypatch):
    """Returns None when subprocess.run raises TimeoutExpired (daemon unresponsive)."""
    monkeypatch.delenv("TAILSCALE_HOSTNAME", raising=False)

    with patch(
        "subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd=["tailscale"], timeout=2.0),
    ):
        result = resolve_tailscale_hostname()

    assert result is None


def test_resolve_tailscale_hostname_nonzero_returncode_returns_none(monkeypatch):
    """Returns None when tailscale exits non-zero (daemon not running)."""
    monkeypatch.delenv("TAILSCALE_HOSTNAME", raising=False)

    with patch(
        "subprocess.run",
        return_value=_completed(returncode=1, stdout="", stderr="daemon not running"),
    ):
        result = resolve_tailscale_hostname()

    assert result is None


def test_resolve_tailscale_hostname_invalid_json_returns_none(monkeypatch):
    """Returns None when subprocess stdout is not valid JSON."""
    monkeypatch.delenv("TAILSCALE_HOSTNAME", raising=False)

    with patch("subprocess.run", return_value=_completed(stdout="not-json!!!")):
        result = resolve_tailscale_hostname()

    assert result is None


def test_resolve_tailscale_hostname_missing_dns_name_returns_none(monkeypatch):
    """Returns None when JSON parses but Self.DNSName is absent."""
    monkeypatch.delenv("TAILSCALE_HOSTNAME", raising=False)
    stdout = json.dumps({"Self": {}})

    with patch("subprocess.run", return_value=_completed(stdout=stdout)):
        result = resolve_tailscale_hostname()

    assert result is None


def test_resolve_tailscale_hostname_empty_dns_name_returns_none(monkeypatch):
    """Returns None when Self.DNSName is present but empty string."""
    monkeypatch.delenv("TAILSCALE_HOSTNAME", raising=False)
    stdout = _make_tailscale_stdout("")

    with patch("subprocess.run", return_value=_completed(stdout=stdout)):
        result = resolve_tailscale_hostname()

    assert result is None


# ===========================================================================
# resolve_tailscale_hostname — caching
# ===========================================================================


def test_resolve_tailscale_hostname_cached_after_first_call(monkeypatch):
    """subprocess.run is called exactly once; second call returns the cached value."""
    monkeypatch.delenv("TAILSCALE_HOSTNAME", raising=False)
    stdout = _make_tailscale_stdout("cached-host.ts.net.")

    with patch("subprocess.run", return_value=_completed(stdout=stdout)) as mock_run:
        first = resolve_tailscale_hostname()
        second = resolve_tailscale_hostname()

    assert first == "cached-host.ts.net"
    assert second == "cached-host.ts.net"
    mock_run.assert_called_once()


def test_resolve_tailscale_hostname_none_cached_after_failure(monkeypatch):
    """None result is also cached: subprocess is not re-run on repeated calls."""
    monkeypatch.delenv("TAILSCALE_HOSTNAME", raising=False)

    with patch("subprocess.run", side_effect=FileNotFoundError()) as mock_run:
        first = resolve_tailscale_hostname()
        second = resolve_tailscale_hostname()

    assert first is None
    assert second is None
    mock_run.assert_called_once()


# ===========================================================================
# resolve_advertise_host — priority regression + Tailscale integration
# ===========================================================================


def test_resolve_advertise_host_env_var_wins_over_all(monkeypatch):
    """JARVIS_MCP_ADVERTISE_HOST env var takes priority over config and Tailscale."""
    monkeypatch.setenv("JARVIS_MCP_ADVERTISE_HOST", "explicit.host.example")
    mcp_config = {"advertise_host": "config-host", "bind_host": "127.0.0.1"}

    with patch.object(device_module, "resolve_tailscale_hostname", return_value="ts-host"):
        result = resolve_advertise_host(mcp_config)

    assert result == "explicit.host.example"


def test_resolve_advertise_host_config_wins_over_tailscale(monkeypatch):
    """mcp_config['advertise_host'] wins over Tailscale auto-detect when env var is absent."""
    monkeypatch.delenv("JARVIS_MCP_ADVERTISE_HOST", raising=False)
    mcp_config = {"advertise_host": "config-host.example", "bind_host": "127.0.0.1"}

    with patch.object(device_module, "resolve_tailscale_hostname", return_value="ts-host"):
        result = resolve_advertise_host(mcp_config)

    assert result == "config-host.example"


def test_resolve_advertise_host_tailscale_autodetect_used(monkeypatch):
    """Tailscale auto-detect is used when both env var and config advertise_host are absent."""
    monkeypatch.delenv("JARVIS_MCP_ADVERTISE_HOST", raising=False)
    mcp_config = {"bind_host": "127.0.0.1"}

    with patch.object(device_module, "resolve_tailscale_hostname", return_value="ts-auto.ts.net"):
        result = resolve_advertise_host(mcp_config)

    assert result == "ts-auto.ts.net"


def test_resolve_advertise_host_falls_back_to_bind_host(monkeypatch):
    """Falls back to mcp_config['bind_host'] when env var, config, and Tailscale all return nothing."""
    monkeypatch.delenv("JARVIS_MCP_ADVERTISE_HOST", raising=False)
    mcp_config = {"bind_host": "192.168.1.50"}

    with patch.object(device_module, "resolve_tailscale_hostname", return_value=None):
        result = resolve_advertise_host(mcp_config)

    assert result == "192.168.1.50"


def test_resolve_advertise_host_falls_back_to_default_loopback(monkeypatch):
    """Falls back to '127.0.0.1' when bind_host is also absent and Tailscale returns nothing."""
    monkeypatch.delenv("JARVIS_MCP_ADVERTISE_HOST", raising=False)
    mcp_config = {}

    with patch.object(device_module, "resolve_tailscale_hostname", return_value=None):
        result = resolve_advertise_host(mcp_config)

    assert result == "127.0.0.1"
