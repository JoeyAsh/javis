"""Google Drive read-only API client for JARVIS.

Wraps the Google Drive REST API v3 via ``googleapiclient``. All blocking
API calls are executed through ``asyncio.to_thread`` so the event loop is
never stalled. Only drive.readonly operations are supported — no write methods.
"""

from __future__ import annotations

import asyncio
import io
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import googleapiclient.discovery

from utils.logger import get_logger

logger = get_logger("drive_client")

# ---------------------------------------------------------------------------
# OAuth scope
# ---------------------------------------------------------------------------

DRIVE_READONLY_SCOPE = "https://www.googleapis.com/auth/drive.readonly"

# Drive API hard cap per page
_MAX_RESULTS_CAP = 100

# MIME type constants
_GOOGLE_DOC_MIME = "application/vnd.google-apps.document"
_GOOGLE_SHEET_MIME = "application/vnd.google-apps.spreadsheet"
_GOOGLE_SLIDE_MIME = "application/vnd.google-apps.presentation"
_PLAIN_TEXT_MIMES = frozenset({"text/plain", "text/markdown", "text/x-markdown"})

# Google Workspace types that can be exported as text/plain
_EXPORTABLE_MIMES = frozenset({_GOOGLE_DOC_MIME, _GOOGLE_SHEET_MIME, _GOOGLE_SLIDE_MIME})

# Fields requested from Drive API for file listings
_FILE_FIELDS = "id, name, mimeType, modifiedTime, webViewLink"


# ---------------------------------------------------------------------------
# Data classes
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
# Exceptions
# ---------------------------------------------------------------------------


class DriveClientError(Exception):
    """Raised when a Drive API call fails in an anticipated way."""

    def __init__(self, message: str, spoken_message: str = "") -> None:
        """Initialise with a technical message and an optional TTS-friendly fallback."""
        super().__init__(message)
        self.spoken_message: str = spoken_message or message


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_drive_file(raw: dict[str, Any]) -> DriveFile:
    """Convert a raw Drive API file dict into a ``DriveFile``."""
    modified_raw: str = raw.get("modifiedTime", "1970-01-01T00:00:00Z")
    try:
        # Drive returns RFC 3339 timestamps; Python 3.11+ fromisoformat handles 'Z'.
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


def _is_text_readable(mime_type: str) -> bool:
    """Return True when the file's content can be fetched as plain text."""
    return mime_type in _PLAIN_TEXT_MIMES or mime_type in _EXPORTABLE_MIMES


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class DriveClient:
    """Async Google Drive read-only client backed by ``googleapiclient``.

    All network I/O is wrapped in ``asyncio.to_thread`` to keep the event
    loop unblocked. The underlying service resource is built lazily on the
    first call and cached for the lifetime of the instance.

    Args:
        oauth_service: Shared ``GoogleOAuthService`` used to obtain credentials
            and build the Drive API resource.
        scopes: OAuth scopes to request (must include ``drive.readonly``).
    """

    def __init__(
        self,
        oauth_service: Any,
        scopes: list[str] | None = None,
    ) -> None:
        """Initialise the client; does not make any network calls."""
        self._oauth_service = oauth_service
        self._scopes: list[str] = scopes or [DRIVE_READONLY_SCOPE]
        self._service: Any | None = None
        self._service_lock: asyncio.Lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Service lifecycle
    # ------------------------------------------------------------------

    async def _get_service(self) -> Any:
        """Return (and lazily build) the authenticated Drive API service."""
        async with self._service_lock:
            if self._service is None:
                logger.debug("Building Drive API service...")
                self._service = await self._oauth_service.build_service(
                    "drive", "v3", scopes=self._scopes
                )
                logger.info("Drive API service ready")
            return self._service

    # ------------------------------------------------------------------
    # Public async API
    # ------------------------------------------------------------------

    async def search(self, query: str, max_results: int = 10) -> list[DriveFile]:
        """Search Drive files using a Drive query string.

        Supports Drive v3 query operators such as ``name contains 'report'``
        or ``fullText contains 'quarterly'``. See the Drive API reference for
        the full syntax.

        Args:
            query: A Drive query expression (e.g. ``"name contains 'budget'"``).
            max_results: Maximum number of results to return (capped at 100).

        Returns:
            List of ``DriveFile`` objects matching the query, ordered by
            relevance (Drive default).

        Raises:
            DriveClientError: On API failure.
        """
        max_results = min(max_results, _MAX_RESULTS_CAP)
        service = await self._get_service()

        try:
            result: dict[str, Any] = await asyncio.to_thread(
                lambda: service.files()
                .list(
                    q=query,
                    pageSize=max_results,
                    fields=f"files({_FILE_FIELDS})",
                    orderBy="relevance",
                )
                .execute()
            )
        except Exception as exc:
            raise DriveClientError(
                f"Drive search failed for query '{query}': {exc}",
                spoken_message="Ich konnte Drive gerade nicht durchsuchen.",
            ) from exc

        files: list[dict[str, Any]] = result.get("files", [])
        parsed = [_parse_drive_file(f) for f in files]
        logger.debug("Drive search '{}' returned {} files", query, len(parsed))
        return parsed

    async def get_file_content(self, file_id: str) -> str:
        """Return plain-text content for a Drive file.

        Supports:
        - Google Docs (exported as ``text/plain``)
        - Google Sheets and Slides (exported as ``text/plain``)
        - Plain text / Markdown files (downloaded directly)

        For non-text MIME types (PDFs, images, etc.) returns an empty string
        and logs a note.

        Args:
            file_id: Drive file ID string.

        Returns:
            Plain-text content string, or ``""`` for binary/non-text files.

        Raises:
            DriveClientError: On API failure while fetching metadata or content.
        """
        service = await self._get_service()

        # Fetch metadata to determine MIME type.
        try:
            meta: dict[str, Any] = await asyncio.to_thread(
                lambda: service.files()
                .get(fileId=file_id, fields="id, name, mimeType")
                .execute()
            )
        except Exception as exc:
            raise DriveClientError(
                f"Failed to fetch metadata for file {file_id}: {exc}",
                spoken_message="Ich konnte die Datei-Metadaten nicht laden.",
            ) from exc

        mime_type: str = meta.get("mimeType", "")
        file_name: str = meta.get("name", file_id)

        if not _is_text_readable(mime_type):
            logger.info(
                "Drive: skipping content for '{}' (mime_type={}) — not a text type",
                file_name,
                mime_type,
            )
            return ""

        try:
            if mime_type in _EXPORTABLE_MIMES:
                # Export Google Workspace document as plain text.
                raw_bytes: bytes = await asyncio.to_thread(
                    lambda: service.files()
                    .export_media(fileId=file_id, mimeType="text/plain")
                    .execute()
                )
            else:
                # Download raw text/markdown file content.
                import googleapiclient.http  # noqa: PLC0415

                request = service.files().get_media(fileId=file_id)
                buf = io.BytesIO()
                downloader = await asyncio.to_thread(
                    googleapiclient.http.MediaIoBaseDownload, buf, request
                )
                done = False
                while not done:
                    _, done = await asyncio.to_thread(downloader.next_chunk)
                raw_bytes = buf.getvalue()

            content = raw_bytes.decode("utf-8", errors="replace") if raw_bytes else ""
            logger.debug(
                "Drive: fetched {} chars from '{}' ({})", len(content), file_name, mime_type
            )
            return content

        except Exception as exc:
            raise DriveClientError(
                f"Failed to fetch content for '{file_name}' ({file_id}): {exc}",
                spoken_message="Ich konnte den Inhalt der Datei nicht laden.",
            ) from exc

    async def list_recent(self, max_results: int = 20) -> list[DriveFile]:
        """Return recently modified Drive files, newest first.

        Args:
            max_results: Maximum number of files to return (capped at 100).

        Returns:
            List of ``DriveFile`` objects ordered by ``modifiedTime`` descending.

        Raises:
            DriveClientError: On API failure.
        """
        max_results = min(max_results, _MAX_RESULTS_CAP)
        service = await self._get_service()

        try:
            result: dict[str, Any] = await asyncio.to_thread(
                lambda: service.files()
                .list(
                    pageSize=max_results,
                    fields=f"files({_FILE_FIELDS})",
                    orderBy="modifiedTime desc",
                )
                .execute()
            )
        except Exception as exc:
            raise DriveClientError(
                f"Drive list_recent failed: {exc}",
                spoken_message="Ich konnte die letzten Drive-Dateien nicht laden.",
            ) from exc

        files: list[dict[str, Any]] = result.get("files", [])
        parsed = [_parse_drive_file(f) for f in files]
        logger.debug("Drive list_recent returned {} files", len(parsed))
        return parsed


# ---------------------------------------------------------------------------
# Module-level lazy factory
# ---------------------------------------------------------------------------

_drive_client_instance: DriveClient | None = None


def get_drive_client(
    scopes: list[str] | None = None,
) -> DriveClient:
    """Return the module-level ``DriveClient`` singleton.

    On first call, builds the instance using the shared ``GoogleOAuthService``
    singleton. Subsequent calls ignore ``scopes`` and return the cached instance.

    Args:
        scopes: Optional scope list for the first-time build. Defaults to
            ``[DRIVE_READONLY_SCOPE]``.

    Returns:
        Shared ``DriveClient`` instance.
    """
    global _drive_client_instance
    if _drive_client_instance is None:
        from integrations.google.oauth import get_google_oauth_service  # noqa: PLC0415

        oauth_service = get_google_oauth_service()
        _drive_client_instance = DriveClient(
            oauth_service=oauth_service,
            scopes=scopes or [DRIVE_READONLY_SCOPE],
        )
        logger.debug("DriveClient singleton created")
    return _drive_client_instance
