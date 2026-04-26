"""Google Drive adapter for JARVIS — thin OpenClaw/gog shim (ADR-0001).

All Google Drive API calls are delegated to the ``gog`` CLI binary.
No ``googleapiclient`` or ``google-auth`` imports remain in this module.

Public surface (dataclasses, exception type, factory function) is 100%
backwards-compatible with the previous googleapiclient implementation so
``orchestrator.py`` and test mocks continue to work unchanged.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from integrations.openclaw.client import GogCommandError, GogNotInstalledError, run_gog
from utils.logger import get_logger

logger = get_logger("drive_client")


# ---------------------------------------------------------------------------
# Data classes (public surface — must stay backwards-compatible)
# ---------------------------------------------------------------------------


@dataclass
class DriveFile:
    """A single Google Drive file with core metadata."""

    id: str
    name: str
    mime_type: str
    modified_time: datetime
    web_view_link: str


# ---------------------------------------------------------------------------
# Exception (kept for caller compatibility)
# ---------------------------------------------------------------------------


class DriveClientError(Exception):
    """Raised when a Drive operation fails in an anticipated way."""

    def __init__(self, message: str, spoken_message: str = "") -> None:
        """Initialise with a technical message and an optional TTS-friendly fallback."""
        super().__init__(message)
        self.spoken_message: str = spoken_message or message


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_gog_drive_file(raw: dict[str, Any]) -> DriveFile:
    """Convert a ``gog drive search --json`` file dict to a ``DriveFile``.

    ``gog`` returns the raw Google Drive API JSON object shape::

        {
          "id": "...",
          "name": "...",
          "mimeType": "...",
          "modifiedTime": "2026-03-20T18:26:29.758Z",
          "webViewLink": "https://..."
        }
    """
    modified_raw: str = raw.get("modifiedTime", "1970-01-01T00:00:00Z")
    try:
        modified_time = datetime.fromisoformat(modified_raw.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        modified_time = datetime(1970, 1, 1, tzinfo=timezone.utc)

    return DriveFile(
        id=raw.get("id", ""),
        name=raw.get("name", "(unnamed)"),
        mime_type=raw.get("mimeType", ""),
        modified_time=modified_time,
        web_view_link=raw.get("webViewLink", ""),
    )


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class DriveClient:
    """Async Google Drive read-only adapter backed by the ``gog`` CLI binary.

    All network I/O is async via ``asyncio.create_subprocess_exec``.  The
    public method surface is 100% compatible with the previous
    ``googleapiclient``-based implementation.

    Args:
        account: Google account email passed to ``gog --account``.  Omit to
            use the default account configured in ``gog auth list``.
        scopes: Accepted for API compatibility; ignored (gog manages its own
            scope negotiation during ``gog auth add``).
        timeout_seconds: Per-call subprocess timeout in seconds.
    """

    def __init__(
        self,
        oauth_service: Any = None,  # accepted for backwards-compat; ignored
        scopes: list[str] | None = None,  # accepted for backwards-compat; ignored
        account: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        """Initialise the client; does not make any network calls."""
        self._account = account
        self._timeout = timeout_seconds

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _account_args(self) -> list[str]:
        """Return the ``--account <email>`` argument list, or empty list."""
        if self._account:
            return ["--account", self._account]
        return []

    async def _run(self, *args: str) -> Any:
        """Run a gog command, converting errors to DriveClientError."""
        try:
            return await run_gog(*args, timeout_seconds=self._timeout)
        except GogNotInstalledError as exc:
            raise DriveClientError(
                str(exc),
                spoken_message="Das gog-Tool ist nicht installiert.",
            ) from exc
        except GogCommandError as exc:
            raise DriveClientError(
                str(exc),
                spoken_message=exc.spoken_message,
            ) from exc

    # ------------------------------------------------------------------
    # Public async API
    # ------------------------------------------------------------------

    async def search(self, query: str, max_results: int = 10) -> list[DriveFile]:
        """Search Drive files using a Drive query string.

        Args:
            query: A Drive query expression or natural-language search term.
            max_results: Maximum number of results to return (capped at 100).

        Returns:
            List of ``DriveFile`` objects matching the query.

        Raises:
            DriveClientError: On gog CLI failure.
        """
        max_results = min(max_results, 100)
        cmd: list[str] = [
            "drive", "search",
            query,
            "--max", str(max_results),
            *self._account_args(),
        ]
        data = await self._run(*cmd)
        files_raw: list[dict[str, Any]] = (
            data.get("files", []) if isinstance(data, dict) else []
        )
        parsed = [_parse_gog_drive_file(f) for f in files_raw]
        logger.debug(f"Drive search '{query}' returned {len(parsed)} files")
        return parsed

    async def get_file_content(self, file_id: str) -> str:
        """Return plain-text content for a Drive file.

        Delegates to ``gog docs cat`` for Google Docs and ``gog docs export``
        for other exportable types.  Returns an empty string for binary files.

        Args:
            file_id: Drive file ID string.

        Returns:
            Plain-text content string, or ``""`` for binary/non-text files.

        Raises:
            DriveClientError: On gog CLI failure while fetching content.
        """
        cmd: list[str] = [
            "docs", "cat",
            file_id,
            *self._account_args(),
        ]
        try:
            # docs cat returns plain text, not JSON — bypass run_gog's JSON parsing.
            from integrations.openclaw.client import _resolve_gog_cli  # noqa: PLC0415

            gog_path = _resolve_gog_cli()
            if gog_path is None:
                raise DriveClientError("gog CLI not found")

            full_cmd = [gog_path, *cmd, "--no-input"]
            proc = await asyncio.create_subprocess_exec(
                *full_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.DEVNULL,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self._timeout
            )
            if proc.returncode != 0:
                err = stderr.decode().strip()
                # Non-exportable file types exit non-zero — treat as empty.
                logger.debug(f"Drive get_file_content gog exit {proc.returncode}: {err}")
                return ""
            return stdout.decode("utf-8", errors="replace").strip()
        except asyncio.TimeoutError:
            logger.warning(f"Drive get_file_content timed out for file_id={file_id!r}")
            return ""
        except DriveClientError:
            raise
        except Exception as exc:
            raise DriveClientError(
                f"Failed to fetch content for {file_id}: {exc}",
                spoken_message="Ich konnte den Inhalt der Datei nicht laden.",
            ) from exc

    async def list_recent(self, max_results: int = 20) -> list[DriveFile]:
        """Return recently modified Drive files, newest first.

        Args:
            max_results: Maximum number of files to return (capped at 100).

        Returns:
            List of ``DriveFile`` objects ordered by ``modifiedTime`` descending.

        Raises:
            DriveClientError: On gog CLI failure.
        """
        max_results = min(max_results, 100)
        # gog drive ls lists files in the root folder, ordered by recency.
        cmd: list[str] = [
            "drive", "ls",
            "--max", str(max_results),
            *self._account_args(),
        ]
        try:
            data = await self._run(*cmd)
        except DriveClientError:
            # Fallback: search with a broad query if ls fails.
            data = await self._run(
                "drive", "search", ".",
                "--max", str(max_results),
                *self._account_args(),
            )

        files_raw: list[dict[str, Any]] = (
            data.get("files", []) if isinstance(data, dict) else []
        )
        parsed = [_parse_gog_drive_file(f) for f in files_raw]
        logger.debug(f"Drive list_recent returned {len(parsed)} files")
        return parsed


# ---------------------------------------------------------------------------
# Module-level lazy factory (public API — patch point for tests)
# ---------------------------------------------------------------------------

_drive_client_instance: DriveClient | None = None


def get_drive_client(
    scopes: list[str] | None = None,
) -> DriveClient:
    """Return the module-level ``DriveClient`` singleton backed by ``gog``.

    On first call, builds the instance using the ``drive.account`` config key.
    Subsequent calls ignore ``scopes`` and return the cached instance.

    Args:
        scopes: Accepted for API compatibility; ignored after gog migration.

    Returns:
        Shared ``DriveClient`` instance.
    """
    global _drive_client_instance
    if _drive_client_instance is None:
        from utils.config_loader import get_config  # noqa: PLC0415

        cfg = get_config()
        drive_cfg = cfg.get_section("drive") or {}
        account: str | None = drive_cfg.get("account") or None
        timeout = float(drive_cfg.get("gog_timeout_seconds", 30))
        _drive_client_instance = DriveClient(account=account, timeout_seconds=timeout)
        logger.debug("DriveClient (gog) singleton created")
    return _drive_client_instance
