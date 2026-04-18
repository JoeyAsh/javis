"""Gmail API client for JARVIS.

Wraps the Google Gmail REST API via ``googleapiclient``. All blocking
API calls are executed through ``asyncio.to_thread`` so the event loop is
never stalled. Summarisation and natural-language generation are *not*
the responsibility of this module — that belongs to the orchestrator.
"""

from __future__ import annotations

import asyncio
import base64
import email.mime.text
import email.utils
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.header import decode_header
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import googleapiclient.discovery

from utils.logger import get_logger

logger = get_logger("gmail_client")

# ---------------------------------------------------------------------------
# OAuth scopes
# ---------------------------------------------------------------------------

GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"

GMAIL_SCOPES: list[str] = [GMAIL_READONLY_SCOPE, GMAIL_SEND_SCOPE]

# Gmail API hard caps
_MAX_RESULTS_CAP = 50


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class EmailMessage:
    """A single Gmail message with parsed headers and optional body."""

    id: str
    thread_id: str
    subject: str
    sender: str
    sender_email: str
    recipient: str
    received_at: datetime
    snippet: str
    body_text: str | None
    is_unread: bool
    is_vip: bool


@dataclass
class EmailDraft:
    """A Gmail draft envelope returned after creation."""

    id: str
    to: str
    subject: str
    body: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class GmailClientError(Exception):
    """Raised when a Gmail API call fails in an anticipated way."""

    def __init__(self, message: str, spoken_message: str = "") -> None:
        """Initialise with a technical message and an optional TTS-friendly fallback."""
        super().__init__(message)
        self.spoken_message: str = spoken_message or message


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _decode_header_value(raw: str) -> str:
    """Decode a possibly RFC-2047-encoded header value to a plain string."""
    parts = decode_header(raw)
    decoded_parts: list[str] = []
    for chunk, charset in parts:
        if isinstance(chunk, bytes):
            decoded_parts.append(chunk.decode(charset or "utf-8", errors="replace"))
        else:
            decoded_parts.append(chunk)
    return "".join(decoded_parts)


def _parse_sender(raw_from: str) -> tuple[str, str]:
    """Split a ``From:`` header into (display_name, email_address).

    Returns:
        Tuple of (display_name, email) — display_name falls back to email
        when no name component is present.
    """
    name, addr = email.utils.parseaddr(raw_from)
    name = _decode_header_value(name) if name else ""
    addr = addr.lower().strip()
    display = name or addr
    return display, addr


def _header_value(headers: list[dict[str, str]], name: str) -> str:
    """Return the value of the first matching header, or empty string."""
    name_lower = name.lower()
    for h in headers:
        if h.get("name", "").lower() == name_lower:
            return h.get("value", "")
    return ""


def _extract_body_text(payload: dict[str, Any]) -> str | None:
    """Recursively extract plain-text body from a Gmail message payload."""
    mime_type: str = payload.get("mimeType", "")
    body: dict[str, Any] = payload.get("body", {})
    data: str = body.get("data", "")

    if mime_type == "text/plain" and data:
        try:
            return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
        except Exception:
            return None

    for part in payload.get("parts", []):
        result = _extract_body_text(part)
        if result is not None:
            return result

    return None


def _parse_message(
    raw: dict[str, Any],
    vip_senders: list[str],
    *,
    include_body: bool = False,
) -> EmailMessage:
    """Convert a raw Gmail API message dict into an ``EmailMessage``."""
    headers: list[dict[str, str]] = raw.get("payload", {}).get("headers", [])

    raw_from = _header_value(headers, "From")
    sender_display, sender_email = _parse_sender(raw_from)

    subject = _decode_header_value(_header_value(headers, "Subject")) or "(no subject)"
    recipient = _header_value(headers, "To")

    # Internal date is milliseconds since epoch
    internal_date_ms = int(raw.get("internalDate", 0))
    received_at = datetime.fromtimestamp(internal_date_ms / 1000, tz=timezone.utc)

    label_ids: list[str] = raw.get("labelIds", [])
    is_unread = "UNREAD" in label_ids

    snippet = raw.get("snippet", "")

    body_text: str | None = None
    if include_body:
        body_text = _extract_body_text(raw.get("payload", {}))

    is_vip = sender_email in [v.lower() for v in vip_senders]

    return EmailMessage(
        id=raw.get("id", ""),
        thread_id=raw.get("threadId", ""),
        subject=subject,
        sender=sender_display,
        sender_email=sender_email,
        recipient=recipient,
        received_at=received_at,
        snippet=snippet,
        body_text=body_text,
        is_unread=is_unread,
        is_vip=is_vip,
    )


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class GmailClient:
    """Async Gmail API client backed by ``googleapiclient``.

    All network I/O is wrapped in ``asyncio.to_thread`` to keep the event
    loop unblocked. The underlying ``googleapiclient.discovery.Resource`` is
    built lazily on the first call that needs it and then cached for the
    lifetime of the instance.

    Args:
        oauth_service: Shared ``GoogleOAuthService`` used to obtain credentials
            and build the service resource.
        vip_senders: List of email addresses that should be flagged as VIP.
    """

    def __init__(
        self,
        oauth_service: Any,  # GoogleOAuthService — avoid circular import in type hint
        vip_senders: list[str],
    ) -> None:
        """Initialise the client; does not make any network calls."""
        self._oauth_service = oauth_service
        self._vip_senders: list[str] = [v.lower() for v in vip_senders]
        self._service: Any | None = None
        self._service_lock: asyncio.Lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Service lifecycle
    # ------------------------------------------------------------------

    async def _get_service(self) -> Any:
        """Return (and lazily build) the authenticated Gmail API service."""
        async with self._service_lock:
            if self._service is None:
                logger.debug("Building Gmail API service...")
                self._service = await self._oauth_service.build_service(
                    "gmail", "v1", scopes=GMAIL_SCOPES
                )
                logger.info("Gmail API service ready")
            return self._service

    # ------------------------------------------------------------------
    # Public async API
    # ------------------------------------------------------------------

    async def list_unread(
        self,
        max_results: int = 5,
        sender: str | None = None,
    ) -> list[EmailMessage]:
        """Return unread messages from the inbox, newest first.

        Args:
            max_results: Maximum number of messages to return (capped at 50).
            sender: Optional sender filter appended to the Gmail query.

        Returns:
            List of ``EmailMessage`` objects with ``is_unread=True``.

        Raises:
            GmailClientError: On API failure.
        """
        max_results = min(max_results, _MAX_RESULTS_CAP)
        query = "is:unread in:inbox"
        if sender:
            query += f" from:{sender}"
        return await self.search(query, max_results=max_results)

    async def search(
        self,
        query: str,
        max_results: int = 10,
    ) -> list[EmailMessage]:
        """Search Gmail with a raw query string.

        Handles pagination transparently; hard cap at 50 results per call.

        Args:
            query: Gmail search query (e.g. ``"from:alice is:unread"``).
            max_results: Maximum number of results (capped at 50).

        Returns:
            List of ``EmailMessage`` objects matching the query.

        Raises:
            GmailClientError: On API failure.
        """
        max_results = min(max_results, _MAX_RESULTS_CAP)
        service = await self._get_service()

        try:
            ids = await self._fetch_message_ids(service, query, max_results)
        except GmailClientError:
            raise
        except Exception as exc:
            raise GmailClientError(
                f"Gmail search failed: {exc}",
                spoken_message=(
                    "Gmail ist gerade nicht erreichbar, bitte kurz warten."
                ),
            ) from exc

        if not ids:
            return []

        messages: list[EmailMessage] = []
        for msg_id in ids:
            try:
                msg = await self.get_message(msg_id, include_body=False)
                messages.append(msg)
            except GmailClientError as exc:
                logger.warning(f"Skipping message {msg_id}: {exc}")

        return messages

    async def get_message(
        self,
        message_id: str,
        include_body: bool = True,
    ) -> EmailMessage:
        """Fetch a single message by ID, optionally loading the full body.

        Args:
            message_id: Gmail message ID string.
            include_body: When ``True`` the plain-text body is extracted and
                included in ``EmailMessage.body_text``.

        Returns:
            Parsed ``EmailMessage``.

        Raises:
            GmailClientError: When the message cannot be fetched.
        """
        service = await self._get_service()
        try:
            raw: dict[str, Any] = await asyncio.to_thread(
                lambda: service.users()
                .messages()
                .get(userId="me", id=message_id, format="full")
                .execute()
            )
        except Exception as exc:
            raise GmailClientError(
                f"Failed to fetch message {message_id}: {exc}",
                spoken_message="Ich konnte die E-Mail nicht laden.",
            ) from exc

        return _parse_message(raw, self._vip_senders, include_body=include_body)

    async def get_unread_count(self) -> int:
        """Return the approximate number of unread messages.

        Uses a single lightweight API call (``resultSizeEstimate`` only) to
        avoid fetching message data.

        Returns:
            Integer unread count estimate.

        Raises:
            GmailClientError: On API failure.
        """
        service = await self._get_service()
        try:
            result: dict[str, Any] = await asyncio.to_thread(
                lambda: service.users()
                .messages()
                .list(
                    userId="me",
                    labelIds=["UNREAD"],
                    maxResults=1,
                    fields="resultSizeEstimate",
                )
                .execute()
            )
        except Exception as exc:
            raise GmailClientError(
                f"Failed to fetch unread count: {exc}",
                spoken_message="Ich konnte die Anzahl ungelesener E-Mails nicht abrufen.",
            ) from exc

        return int(result.get("resultSizeEstimate", 0))

    async def create_draft(
        self,
        to: str,
        subject: str,
        body: str,
    ) -> EmailDraft:
        """Create a Gmail draft and return the draft envelope.

        Args:
            to: Recipient address (e.g. ``"alice@example.com"``).
            subject: Email subject line.
            body: Plain-text email body.

        Returns:
            ``EmailDraft`` with the new draft ID.

        Raises:
            GmailClientError: When the draft cannot be created.
        """
        if not to or not to.strip():
            raise GmailClientError(
                "Draft creation requires a non-empty recipient address.",
                spoken_message=(
                    "Ich konnte den Entwurf nicht erstellen — "
                    "bitte geben Sie eine gültige Empfängeradresse an."
                ),
            )

        mime_msg = email.mime.text.MIMEText(body, "plain", "utf-8")
        mime_msg["To"] = to
        mime_msg["Subject"] = subject
        raw_bytes = base64.urlsafe_b64encode(mime_msg.as_bytes()).decode("utf-8")

        service = await self._get_service()
        try:
            result: dict[str, Any] = await asyncio.to_thread(
                lambda: service.users()
                .drafts()
                .create(userId="me", body={"message": {"raw": raw_bytes}})
                .execute()
            )
        except Exception as exc:
            raise GmailClientError(
                f"Failed to create draft: {exc}",
                spoken_message="Ich konnte den E-Mail-Entwurf nicht erstellen.",
            ) from exc

        draft_id: str = result.get("id", "")
        logger.info(f"Gmail draft created: id={draft_id} to={to!r} subject={subject!r}")
        return EmailDraft(id=draft_id, to=to, subject=subject, body=body)

    async def send_draft(self, draft_id: str) -> str:
        """Send an existing draft by its ID.

        Args:
            draft_id: Gmail draft ID returned by ``create_draft``.

        Returns:
            Sent message ID (Gmail message ID, not draft ID).

        Raises:
            GmailClientError: When the send call fails.
        """
        service = await self._get_service()
        try:
            result: dict[str, Any] = await asyncio.to_thread(
                lambda: service.users()
                .drafts()
                .send(userId="me", body={"id": draft_id})
                .execute()
            )
        except Exception as exc:
            raise GmailClientError(
                f"Failed to send draft {draft_id}: {exc}",
                spoken_message=(
                    "Senden fehlgeschlagen, Sir. Die Nachricht wurde nicht gesendet."
                ),
            ) from exc

        message_id: str = result.get("id", "")
        logger.info(f"Gmail draft sent: draft_id={draft_id} message_id={message_id}")
        return message_id

    async def delete_draft(self, draft_id: str) -> bool:
        """Delete a draft by its ID (e.g. on send abort).

        Args:
            draft_id: Gmail draft ID.

        Returns:
            ``True`` on success, ``False`` on failure (non-fatal).
        """
        service = await self._get_service()
        try:
            await asyncio.to_thread(
                lambda: service.users()
                .drafts()
                .delete(userId="me", id=draft_id)
                .execute()
            )
            logger.info(f"Gmail draft deleted: draft_id={draft_id}")
            return True
        except Exception as exc:
            logger.warning(f"Failed to delete draft {draft_id}: {exc}")
            return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _fetch_message_ids(
        self,
        service: Any,
        query: str,
        max_results: int,
    ) -> list[str]:
        """Fetch message IDs matching ``query`` (pagination-aware).

        Args:
            service: Authenticated Gmail service resource.
            query: Gmail query string.
            max_results: Maximum number of IDs to collect.

        Returns:
            List of message ID strings, up to ``max_results``.
        """
        ids: list[str] = []
        page_token: str | None = None

        while len(ids) < max_results:
            batch_size = min(max_results - len(ids), 100)
            kwargs: dict[str, Any] = {
                "userId": "me",
                "q": query,
                "maxResults": batch_size,
            }
            if page_token:
                kwargs["pageToken"] = page_token

            page: dict[str, Any] = await asyncio.to_thread(
                lambda kw=kwargs: service.users().messages().list(**kw).execute()
            )
            messages: list[dict[str, Any]] = page.get("messages", [])
            ids.extend(m["id"] for m in messages if "id" in m)

            page_token = page.get("nextPageToken")
            if not page_token:
                break

        return ids[:max_results]


# ---------------------------------------------------------------------------
# Module-level lazy factory
# ---------------------------------------------------------------------------

_gmail_client_instance: GmailClient | None = None


def get_gmail_client(
    vip_senders: list[str] | None = None,
) -> GmailClient:
    """Return the module-level ``GmailClient`` singleton.

    On first call, builds the instance using the shared ``GoogleOAuthService``
    singleton. Subsequent calls ignore ``vip_senders`` and return the cached
    instance.

    Args:
        vip_senders: Optional list of VIP email addresses for the first-time
            build. Defaults to an empty list.

    Returns:
        Shared ``GmailClient`` instance.
    """
    global _gmail_client_instance
    if _gmail_client_instance is None:
        from integrations.google.oauth import get_google_oauth_service

        oauth_service = get_google_oauth_service()
        _gmail_client_instance = GmailClient(
            oauth_service=oauth_service,
            vip_senders=vip_senders or [],
        )
        logger.debug("GmailClient singleton created")
    return _gmail_client_instance
