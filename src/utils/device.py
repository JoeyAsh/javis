"""Device identity utilities for JARVIS multi-device awareness.

Provides stable, human-readable device slugs derived from an environment
variable override or the machine hostname, and resolves the advertise host
for the MCP SSE URL.  Both helpers are used at startup by ``api.mcp_server``
and ``api.ws_server`` so that every JARVIS instance registers with OpenClaw
under a unique, reachable name without any hardcoded defaults.
"""

from __future__ import annotations

import json
import os
import re
import socket
import subprocess
from pathlib import Path
from typing import Any

from utils.logger import get_logger

logger = get_logger("device")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_OPENCLAW_DEVICE_FILE = Path.home() / ".openclaw" / "identity" / "device.json"
_MAX_SLUG_LEN = 40
_SLUG_FALLBACK = "jarvis"

# Cache for Tailscale hostname lookup — None means "not yet resolved",
# empty string means "resolved but not found".
_tailscale_hostname_cache: str | None = None
_tailscale_hostname_resolved: bool = False


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def resolve_device_slug() -> str:
    """Derive a stable, sanitized slug for this JARVIS instance.

    Resolution order:
      1. ``JARVIS_DEVICE_NAME`` env var (stripped, lowercased, sanitized).
      2. ``socket.gethostname()`` with the same sanitization.

    Sanitization rules:
      - Lowercase.
      - Spaces and underscores replaced with ``-``.
      - All characters not matching ``[a-z0-9-]`` stripped.
      - Consecutive ``-`` collapsed to one.
      - Leading and trailing ``-`` stripped.
      - Truncated to 40 characters.
      - If the result is empty, returns ``"jarvis"``.

    Returns:
        Sanitized slug string, at least ``"jarvis"``.
    """
    raw = os.environ.get("JARVIS_DEVICE_NAME", "").strip() or socket.gethostname()
    slug = _sanitize_slug(raw)

    if not slug:
        logger.warning(
            f"Device slug resolved to empty string from {raw!r}; "
            f"falling back to '{_SLUG_FALLBACK}'"
        )
        return _SLUG_FALLBACK

    if len(raw) != len(slug):
        logger.debug(f"Device slug sanitized: {raw!r} → {slug!r}")

    if len(slug) == _MAX_SLUG_LEN and len(_sanitize_slug(raw)) >= _MAX_SLUG_LEN:
        logger.info(
            f"Device slug truncated to {_MAX_SLUG_LEN} chars: {slug!r}. "
            "Set JARVIS_DEVICE_NAME to a shorter value if needed."
        )

    logger.debug(
        f"Device slug may not be unique if other instances share hostname '{slug}'. "
        "Set JARVIS_DEVICE_NAME to disambiguate."
        if not os.environ.get("JARVIS_DEVICE_NAME")
        else f"Device slug set from JARVIS_DEVICE_NAME: {slug!r}"
    )

    return slug


def resolve_tailscale_hostname() -> str | None:
    """Detect this machine's Tailscale MagicDNS hostname via ``tailscale status --json``.

    Tries ``TAILSCALE_HOSTNAME`` env var first (cheap path).  Falls back to
    running the Tailscale CLI with a 2-second timeout and parsing
    ``Self.DNSName`` from the JSON output.  Strips the trailing dot that
    Tailscale appends (e.g. ``"laptop-paps.tailnet.ts.net."`` →
    ``"laptop-paps.tailnet.ts.net"``).

    The result is cached after the first call so subsequent invocations do not
    re-spawn the subprocess.

    Returns:
        Tailscale hostname string, or ``None`` when Tailscale is not installed,
        the daemon is not running, or detection fails for any reason.
    """
    global _tailscale_hostname_cache, _tailscale_hostname_resolved

    if _tailscale_hostname_resolved:
        return _tailscale_hostname_cache or None

    _tailscale_hostname_resolved = True

    # Fast path: explicit env var.
    env_val = os.environ.get("TAILSCALE_HOSTNAME", "").strip()
    if env_val:
        logger.info(f"Tailscale hostname from TAILSCALE_HOSTNAME env var: {env_val!r}")
        _tailscale_hostname_cache = env_val
        return env_val

    # Subprocess path: parse `tailscale status --json`.
    try:
        result = subprocess.run(
            ["tailscale", "status", "--json"],
            timeout=2.0,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            logger.debug(
                f"tailscale status --json returned code {result.returncode}; "
                "Tailscale may not be running"
            )
            return None

        data = json.loads(result.stdout)
        dns_name: str = data.get("Self", {}).get("DNSName", "")
        if dns_name:
            # Strip trailing dot from FQDN.
            hostname = dns_name.rstrip(".")
            logger.info(f"Tailscale hostname auto-detected from CLI: {hostname!r}")
            _tailscale_hostname_cache = hostname
            return hostname

        logger.debug("tailscale status --json: Self.DNSName is empty")
    except FileNotFoundError:
        logger.debug("tailscale CLI not found; skipping Tailscale hostname detection")
    except subprocess.TimeoutExpired:
        logger.debug("tailscale status --json timed out (>2 s); skipping")
    except json.JSONDecodeError as exc:
        logger.debug(f"Failed to parse tailscale status JSON: {exc}")
    except Exception as exc:  # noqa: BLE001
        logger.debug(f"Unexpected error during Tailscale hostname detection: {exc}")

    return None


def resolve_advertise_host(mcp_config: dict[str, Any]) -> str:
    """Return the host to advertise in the MCP SSE URL.

    Resolution order:
      1. ``JARVIS_MCP_ADVERTISE_HOST`` env var.
      2. ``mcp_config['advertise_host']`` when set and not null.
      3. ``TAILSCALE_HOSTNAME`` env var or ``tailscale status --json`` (auto-detect).
      4. ``mcp_config['bind_host']`` (default ``"127.0.0.1"``).

    Args:
        mcp_config: The ``mcp`` section from ``config.yaml``.

    Returns:
        Host string (IP or hostname) to use in the advertised SSE URL.
    """
    env_host = os.environ.get("JARVIS_MCP_ADVERTISE_HOST", "").strip()
    if env_host:
        logger.debug(f"MCP advertise host from env: {env_host!r}")
        return env_host

    config_host = mcp_config.get("advertise_host")
    if config_host:
        logger.debug(f"MCP advertise host from config: {config_host!r}")
        return str(config_host)

    tailscale_host = resolve_tailscale_hostname()
    if tailscale_host:
        logger.info(f"MCP advertise host from Tailscale auto-detect: {tailscale_host!r}")
        return tailscale_host

    bind_host: str = mcp_config.get("bind_host", "127.0.0.1")
    logger.debug(f"MCP advertise host defaults to bind_host: {bind_host!r}")
    return bind_host


def load_device_identity() -> dict[str, Any]:
    """Load the Ed25519 device identity from ``~/.openclaw/identity/device.json``.

    Returns:
        Parsed JSON dict from the device identity file, or an empty dict if
        the file does not exist or cannot be parsed.
    """
    try:
        return json.loads(_OPENCLAW_DEVICE_FILE.read_text())
    except FileNotFoundError:
        logger.debug(f"Device identity file not found: {_OPENCLAW_DEVICE_FILE}")
        return {}
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Failed to load device identity from {_OPENCLAW_DEVICE_FILE}: {exc}")
        return {}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _sanitize_slug(raw: str) -> str:
    """Apply slug normalization rules and return the sanitized result.

    Args:
        raw: Raw string to sanitize (hostname or env-var value).

    Returns:
        Sanitized, truncated slug.
    """
    slug = raw.lower()
    slug = slug.replace(" ", "-").replace("_", "-")
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    slug = re.sub(r"-{2,}", "-", slug)
    slug = slug.strip("-")
    return slug[:_MAX_SLUG_LEN]
