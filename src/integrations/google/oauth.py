"""Google OAuth shim — exception hierarchy only (OpenClaw-first migration).

After the migration to the ``gog`` CLI adapter (ADR-0001), JARVIS no longer
owns a Google token cache or runs the interactive OAuth flow.  Auth is managed
exclusively by the ``gog auth add`` command on the OpenClaw host.

This module is kept as a **thin shim** that re-exports the exception hierarchy
so existing callers (ws_server.py, orchestrator.py) continue to compile and
their ``except GoogleOAuthError`` blocks remain valid.  No ``googleapiclient``
or ``google-auth`` imports remain here.
"""

from __future__ import annotations

from typing import Any

from utils.logger import get_logger

logger = get_logger("google_oauth_shim")

# ---------------------------------------------------------------------------
# Exception hierarchy (kept for backwards-compatibility with callers)
# ---------------------------------------------------------------------------


class GoogleOAuthError(Exception):
    """Base exception for Google OAuth failures (kept for caller compatibility)."""

    def __init__(self, message: str, spoken_message: str = "") -> None:
        """Initialise with a technical message and an optional TTS-friendly message."""
        super().__init__(message)
        self.spoken_message: str = spoken_message or message


class GoogleOAuthFlowError(GoogleOAuthError):
    """Raised when the interactive OAuth flow fails or is cancelled."""


class GoogleOAuthTokenError(GoogleOAuthError):
    """Raised when token refresh fails and no interactive flow is possible."""


class GoogleOAuthRevokeError(GoogleOAuthError):
    """Raised when token revocation fails."""


# ---------------------------------------------------------------------------
# Stub service (no-op) — satisfies legacy singleton factory callers
# ---------------------------------------------------------------------------


class GoogleOAuthService:
    """No-op OAuth service stub.

    All methods return safe defaults.  Actual auth lives in ``gog``'s own
    token store (``~/.config/gog/`` on the OpenClaw host).
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """Accept config dict for API-compatibility; does nothing."""
        logger.debug(
            "GoogleOAuthService: running in stub mode — auth delegated to gog CLI"
        )

    async def is_authenticated(self, scopes: list[str]) -> bool:
        """Always return True — gog manages its own token; we never gate on this."""
        return True

    async def get_credentials(self, scopes: list[str]) -> None:
        """No-op stub — gog CLI manages auth; this path is never called."""
        return None  # type: ignore[return-value]

    async def revoke(self) -> None:
        """No-op stub — use ``gog auth remove <email>`` to revoke access."""
        logger.info(
            "GoogleOAuthService.revoke(): no-op — use 'gog auth remove <email>' instead"
        )


# ---------------------------------------------------------------------------
# Module-level singleton factory (kept for legacy callers)
# ---------------------------------------------------------------------------

_service_instance: GoogleOAuthService | None = None


def get_google_oauth_service(config: dict[str, Any] | None = None) -> GoogleOAuthService:
    """Return the shared ``GoogleOAuthService`` stub singleton.

    Kept for API-compatibility with legacy callers.  The real auth lives in
    the ``gog`` CLI on the OpenClaw host.

    Args:
        config: Optional config dict (accepted but ignored after migration).

    Returns:
        The singleton ``GoogleOAuthService`` stub instance.
    """
    global _service_instance
    if _service_instance is None:
        _service_instance = GoogleOAuthService(config or {})
        logger.debug("GoogleOAuthService stub singleton created")
    return _service_instance
