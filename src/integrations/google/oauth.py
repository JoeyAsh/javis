"""Google OAuth 2.0 shared foundation for JARVIS.

Provides a single, reusable authentication layer that all Google-service
integrations (Gmail, Calendar, Drive) can consume. Handles the full OAuth 2.0
desktop flow — interactive browser consent on first use, silent token refresh
thereafter, scope-incremental re-consent, and cache-backed persistence.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

import google.auth.exceptions
import google.auth.transport.requests
import google.oauth2.credentials
import googleapiclient.discovery
import requests
from google_auth_oauthlib.flow import InstalledAppFlow
from loguru import logger

# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------

_SCOPE_PREFIX = "https://www.googleapis.com/auth/"


class GoogleOAuthError(Exception):
    """Base exception for Google OAuth failures."""

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
# Helper utilities
# ---------------------------------------------------------------------------


def _normalise_scope(scope: str) -> str:
    """Expand a short-form scope string to a full Google API URI.

    Callers may pass ``"gmail.readonly"`` or the full URI; both are accepted.
    """
    if scope.startswith("https://") or scope.startswith("http://"):
        return scope
    return f"{_SCOPE_PREFIX}{scope}"


def _is_headless() -> bool:
    """Return True when no graphical display is available."""
    return not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY")


# ---------------------------------------------------------------------------
# Service implementation
# ---------------------------------------------------------------------------


class GoogleOAuthService:
    """Shared OAuth 2.0 service for all Google integrations.

    Handles first-use browser consent, silent token refresh, scope-incremental
    re-consent, and local token cache persistence. All public methods are
    async; blocking library calls are delegated to ``asyncio.to_thread``.

    Args:
        config: Merged dict from the ``google:`` section of ``config.yaml``.
                Env vars ``GOOGLE_OAUTH_CLIENT_ID``, ``GOOGLE_OAUTH_CLIENT_SECRET``,
                and ``GOOGLE_TOKEN_CACHE`` override the corresponding config keys
                when present.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """Resolve credentials, cache path, and timeout from config + env."""
        # Client credentials — env wins over config
        self._client_id: str = os.environ.get(
            "GOOGLE_OAUTH_CLIENT_ID", config.get("client_id", "")
        )
        self._client_secret: str = os.environ.get(
            "GOOGLE_OAUTH_CLIENT_SECRET", config.get("client_secret", "")
        )

        # Token cache path — env wins over config; default to ~/.jarvis/google_token.json
        raw_cache_path: str = os.environ.get(
            "GOOGLE_TOKEN_CACHE",
            config.get("token_cache_path", "~/.jarvis/google_token.json"),
        )
        self._token_cache_path: Path = Path(raw_cache_path).expanduser().resolve()

        # Timeout for the interactive flow only (seconds)
        self._timeout_seconds: int = int(config.get("timeout_seconds", 120))

        # Lock prevents two simultaneous interactive flows
        self._flow_lock: asyncio.Lock = asyncio.Lock()

        # Eagerly create the cache directory so first-use write never fails.
        # This is done at construction time per the spec's edge-case note;
        # it is NOT a top-level module side effect.
        self._token_cache_path.parent.mkdir(parents=True, exist_ok=True)

        logger.debug(
            "GoogleOAuthService initialised | cache={} | timeout={}s",
            self._token_cache_path,
            self._timeout_seconds,
        )

    # ------------------------------------------------------------------
    # Public async API
    # ------------------------------------------------------------------

    async def get_credentials(self, scopes: list[str]) -> google.oauth2.credentials.Credentials:
        """Return valid credentials covering all requested scopes.

        Runs the interactive flow if needed, refreshes expired tokens silently,
        and triggers re-auth when cached scopes are insufficient.

        Args:
            scopes: OAuth scope strings, e.g.
                ``["https://www.googleapis.com/auth/gmail.readonly"]``.

        Returns:
            A valid, non-expired ``Credentials`` object.

        Raises:
            GoogleOAuthFlowError: Flow was cancelled, timed out, or failed.
            GoogleOAuthTokenError: Refresh failed and no interactive flow is
                available.
        """
        normalised_scopes = [_normalise_scope(s) for s in scopes]

        creds = await self._load_cached_credentials()

        if creds is not None:
            # Check scope coverage
            cached_scope_set = set(creds.scopes or [])
            requested_scope_set = set(normalised_scopes)

            if requested_scope_set.issubset(cached_scope_set):
                # All requested scopes are covered
                if creds.valid:
                    logger.debug("Token cache hit — returning valid credentials")
                    return creds

                if creds.expired and creds.refresh_token:
                    logger.debug("Token expired — attempting silent refresh")
                    return await self._refresh_credentials(creds)

            else:
                missing = requested_scope_set - cached_scope_set
                logger.info(
                    "Cached token missing scopes {} — triggering re-auth", missing
                )
                creds = None  # force interactive flow

        # No usable credentials — run the interactive flow
        return await self._run_interactive_flow(normalised_scopes)

    async def is_authenticated(self, scopes: list[str]) -> bool:
        """Return True if a cached, valid token covering all scopes exists.

        Does NOT trigger the interactive flow.

        Args:
            scopes: Scope strings to check coverage for.

        Returns:
            True if authenticated and token is not expired, False otherwise.
        """
        normalised_scopes = [_normalise_scope(s) for s in scopes]

        try:
            creds = await self._load_cached_credentials()
        except Exception as exc:
            logger.warning("is_authenticated: error loading cache — {}", exc)
            return False

        if creds is None:
            return False

        cached_scope_set = set(creds.scopes or [])
        if not set(normalised_scopes).issubset(cached_scope_set):
            return False

        return bool(creds.valid)

    async def revoke(self) -> None:
        """Revoke the stored token and delete the cache file.

        Calls Google's token revocation endpoint, then removes the local
        token file regardless of revocation outcome.

        Raises:
            GoogleOAuthRevokeError: If revocation request fails with a
                non-recoverable error.
        """
        if not self._token_cache_path.exists():
            logger.info("revoke(): no token cache file found — nothing to revoke")
            return

        creds = await self._load_cached_credentials()

        if creds is not None and creds.token:
            try:
                await asyncio.to_thread(self._sync_revoke, creds)
                logger.info("Google token revoked successfully")
            except GoogleOAuthRevokeError:
                # Delete local file even when revocation fails so JARVIS is clean
                self._delete_cache_file()
                raise
        else:
            logger.info("revoke(): no active token to revoke remotely")

        self._delete_cache_file()

    async def build_service(
        self,
        api_name: str,
        api_version: str,
        scopes: list[str],
    ) -> googleapiclient.discovery.Resource:
        """Return a ready-to-use Google API Resource object.

        Calls ``get_credentials`` internally; callers do not need to handle
        credentials directly.

        Args:
            api_name: e.g. ``"gmail"``
            api_version: e.g. ``"v1"``
            scopes: Required scopes for this service.

        Returns:
            Authenticated ``googleapiclient.discovery.Resource``.

        Raises:
            GoogleOAuthFlowError: Propagated from ``get_credentials``.
            GoogleOAuthTokenError: Propagated from ``get_credentials``.
        """
        creds = await self.get_credentials(scopes)
        resource: googleapiclient.discovery.Resource = await asyncio.to_thread(
            googleapiclient.discovery.build, api_name, api_version, credentials=creds
        )
        logger.debug("Built Google API resource | api={} version={}", api_name, api_version)
        return resource

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _load_cached_credentials(
        self,
    ) -> google.oauth2.credentials.Credentials | None:
        """Load credentials from the token cache file.

        Returns ``None`` when the file does not exist or is corrupt; a warning
        is logged for the corrupt case and the file is deleted.
        """
        if not self._token_cache_path.exists():
            return None

        try:
            raw = await asyncio.to_thread(self._token_cache_path.read_text, encoding="utf-8")
            data = json.loads(raw)
            creds = google.oauth2.credentials.Credentials(
                token=data.get("token"),
                refresh_token=data.get("refresh_token"),
                token_uri=data.get("token_uri", "https://oauth2.googleapis.com/token"),
                client_id=data.get("client_id") or self._client_id,
                client_secret=data.get("client_secret") or self._client_secret,
                scopes=data.get("scopes"),
            )
            return creds
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            logger.warning(
                "Token cache is corrupt ({}); discarding and triggering fresh flow",
                exc,
            )
            self._delete_cache_file()
            return None

    async def _refresh_credentials(
        self, creds: google.oauth2.credentials.Credentials
    ) -> google.oauth2.credentials.Credentials:
        """Silently refresh an expired credential using its refresh token.

        Raises:
            GoogleOAuthTokenError: If the refresh request fails.
        """
        try:
            request = google.auth.transport.requests.Request()
            await asyncio.to_thread(creds.refresh, request)
            await self._persist_credentials(creds)
            logger.info("Google token refreshed and persisted")
            return creds
        except google.auth.exceptions.RefreshError as exc:
            msg = str(exc)
            if "clock" in msg.lower():
                logger.error(
                    "Token refresh failed — possible clock skew detected: {}", msg
                )
            else:
                logger.error("Token refresh failed: {}", msg)
            raise GoogleOAuthTokenError(
                f"Refresh failed: {msg}",
                spoken_message="I couldn't refresh my Google access. Please re-authenticate.",
            ) from exc

    async def _run_interactive_flow(
        self, normalised_scopes: list[str]
    ) -> google.oauth2.credentials.Credentials:
        """Run the InstalledAppFlow, serialising concurrent invocations via lock.

        Raises:
            GoogleOAuthFlowError: Flow cancelled, timed out, or stdin not a tty
                in headless mode.
        """
        async with self._flow_lock:
            # Re-check cache under the lock; a concurrent call may have just
            # completed the flow and written the token.
            creds = await self._load_cached_credentials()
            if creds is not None and creds.valid:
                cached_scope_set = set(creds.scopes or [])
                if set(normalised_scopes).issubset(cached_scope_set):
                    logger.debug("Flow lock released — concurrent call already obtained token")
                    return creds

            if not self._client_id or not self._client_secret:
                raise GoogleOAuthFlowError(
                    "GOOGLE_OAUTH_CLIENT_ID / GOOGLE_OAUTH_CLIENT_SECRET not configured",
                    spoken_message=(
                        "Google credentials are not configured. "
                        "Please set your client ID and secret."
                    ),
                )

            client_config = {
                "installed": {
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
                }
            }

            flow = InstalledAppFlow.from_client_config(client_config, scopes=normalised_scopes)

            headless = _is_headless()
            if headless:
                logger.info(
                    "Headless machine detected — falling back to local server flow "
                    "on 0.0.0.0 (run_console removed in newer google-auth-oauthlib)."
                )
                coro_or_fn = self._run_local_server_flow
            else:
                coro_or_fn = self._run_local_server_flow

            try:
                creds = await asyncio.wait_for(
                    asyncio.to_thread(coro_or_fn, flow),
                    timeout=self._timeout_seconds,
                )
            except asyncio.TimeoutError as exc:
                raise GoogleOAuthFlowError(
                    f"Interactive OAuth flow timed out after {self._timeout_seconds}s",
                    spoken_message="Google sign-in timed out. Please try again.",
                ) from exc
            except GoogleOAuthFlowError:
                raise
            except Exception as exc:
                raise GoogleOAuthFlowError(
                    f"OAuth flow failed: {exc}",
                    spoken_message="Google sign-in was cancelled. Please try again.",
                ) from exc

            if creds is None:
                raise GoogleOAuthFlowError(
                    "OAuth flow returned no credentials",
                    spoken_message="Google sign-in was cancelled. Please try again.",
                )

            await self._persist_credentials(creds)
            logger.info("Google OAuth flow completed — credentials persisted")
            return creds

    @staticmethod
    def _run_local_server_flow(
        flow: InstalledAppFlow,
    ) -> google.oauth2.credentials.Credentials:
        """Blocking helper — run browser-based flow (called via asyncio.to_thread)."""
        # port=0 lets the OS pick a free ephemeral port (no collision risk)
        return flow.run_local_server(port=0)

    @staticmethod
    def _run_console_flow(
        flow: InstalledAppFlow,
    ) -> google.oauth2.credentials.Credentials:
        """Blocking helper — run console-based flow (called via asyncio.to_thread)."""
        try:
            return flow.run_console()
        except (EOFError, OSError) as exc:
            raise GoogleOAuthFlowError(
                f"Console flow failed (stdin not a tty?): {exc}",
                spoken_message=(
                    "Google sign-in requires either a display or an interactive terminal."
                ),
            ) from exc

    async def _persist_credentials(self, creds: google.oauth2.credentials.Credentials) -> None:
        """Write credentials to the token cache file as JSON."""
        data = {
            "token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scopes": list(creds.scopes) if creds.scopes else [],
        }
        payload = json.dumps(data, indent=2)
        await asyncio.to_thread(
            self._token_cache_path.write_text, payload, "utf-8"
        )
        logger.debug("Credentials persisted to {}", self._token_cache_path)

    def _sync_revoke(self, creds: google.oauth2.credentials.Credentials) -> None:
        """Blocking revocation call — run via asyncio.to_thread by caller."""
        try:
            resp = requests.post(
                "https://oauth2.googleapis.com/revoke",
                params={"token": creds.token},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10,
            )
        except requests.exceptions.RequestException as exc:
            raise GoogleOAuthRevokeError(
                f"Revocation request failed (network error): {exc}",
                spoken_message=(
                    "I couldn't sign out of Google right now. "
                    "Your local credentials have been removed."
                ),
            ) from exc
        if resp.status_code not in (200, 204):
            raise GoogleOAuthRevokeError(
                f"Revocation endpoint returned HTTP {resp.status_code}: {resp.text}",
                spoken_message=(
                    "I couldn't sign out of Google right now. "
                    "Your local credentials have been removed."
                ),
            )

    def _delete_cache_file(self) -> None:
        """Remove the token cache file if it exists."""
        try:
            self._token_cache_path.unlink(missing_ok=True)
            logger.info("Token cache file deleted: {}", self._token_cache_path)
        except OSError as exc:
            logger.warning("Could not delete token cache file {}: {}", self._token_cache_path, exc)


# ---------------------------------------------------------------------------
# Module-level singleton factory
# ---------------------------------------------------------------------------

_service_instance: GoogleOAuthService | None = None


def get_google_oauth_service(config: dict[str, Any] | None = None) -> GoogleOAuthService:
    """Return the shared ``GoogleOAuthService`` singleton.

    On first call, creates the instance using ``config`` (which should be the
    ``google:`` section from ``config.yaml``). Subsequent calls return the
    cached instance regardless of the ``config`` argument.

    Args:
        config: Optional config dict for first-time initialisation. Defaults
                to an empty dict when omitted (env vars still apply).

    Returns:
        The singleton ``GoogleOAuthService`` instance.
    """
    global _service_instance
    if _service_instance is None:
        _service_instance = GoogleOAuthService(config or {})
        logger.debug("GoogleOAuthService singleton created")
    return _service_instance
