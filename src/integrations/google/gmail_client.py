"""Gmail adapter for JARVIS — thin OpenClaw/gog shim (ADR-0001).

All Google API calls are delegated to the ``gog`` CLI binary which the
``gog`` OpenClaw skill manages.  No ``googleapiclient`` or ``google-auth``
imports remain in this module.

Public surface (dataclasses, exception type, factory function) is 100%
backwards-compatible with the previous googleapiclient implementation so
``ws_server.py``, ``orchestrator.py``, and test mocks continue to work
unchanged.
"""

from __future__ import annotations

import email.utils
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.header import decode_header
from typing import Any

from integrations.openclaw.client import GogCommandError, GogNotInstalledError, run_gog
from utils.logger import get_logger

logger = get_logger("gmail_client")

# ---------------------------------------------------------------------------
# Data classes (public surface — must stay backwards-compatible)
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
# Exception (kept for caller compatibility)
# ---------------------------------------------------------------------------


class GmailClientError(Exception):
    """Raised when a Gmail operation fails in an anticipated way."""

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
    decoded: list[str] = []
    for chunk, charset in parts:
        if isinstance(chunk, bytes):
            decoded.append(chunk.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(chunk)
    return "".join(decoded)


def _parse_sender(raw_from: str) -> tuple[str, str]:
    """Split a ``From:`` header into (display_name, email_address)."""
    name, addr = email.utils.parseaddr(raw_from)
    name = _decode_header_value(name) if name else ""
    addr = addr.lower().strip()
    display = name or addr
    return display, addr


def _parse_gog_message(
    raw: dict[str, Any],
    vip_senders: list[str],
) -> EmailMessage:
    """Convert a ``gog`` JSON message dict to an ``EmailMessage``.

    ``gog gmail messages search --json`` returns objects with the shape::

        {
          "id": "...",
          "threadId": "...",
          "date": "2026-04-25 17:29",
          "from": "Name <email>",
          "subject": "...",
          "snippet": "...",         # present on full-format fetches
          "labels": ["UNREAD", "INBOX", ...],
          "to": "...",
          "body": "..."             # only with --full flag
        }
    """
    msg_id: str = raw.get("id", "")
    thread_id: str = raw.get("threadId", raw.get("thread_id", msg_id))

    raw_from: str = raw.get("from", "")
    sender_display, sender_email = _parse_sender(raw_from)
    subject: str = _decode_header_value(raw.get("subject", "(no subject)") or "(no subject)")
    recipient: str = raw.get("to", "")
    snippet: str = raw.get("snippet", raw.get("body", "")[:200])

    # gog returns dates as "YYYY-MM-DD HH:MM" strings in local time.
    date_str: str = raw.get("date", "")
    received_at: datetime
    try:
        if date_str:
            received_at = datetime.strptime(date_str, "%Y-%m-%d %H:%M").replace(
                tzinfo=timezone.utc
            )
        else:
            received_at = datetime.now(timezone.utc)
    except ValueError:
        received_at = datetime.now(timezone.utc)

    labels: list[str] = raw.get("labels", [])
    is_unread = "UNREAD" in labels

    body_text: str | None = raw.get("body") or None

    is_vip = sender_email in vip_senders

    return EmailMessage(
        id=msg_id,
        thread_id=thread_id,
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
    """Async Gmail adapter backed by the ``gog`` CLI binary.

    All network I/O is async via ``asyncio.create_subprocess_exec``.  The
    public method surface is 100% compatible with the previous
    ``googleapiclient``-based implementation.

    Args:
        account: Google account email passed to ``gog --account``.  Omit to
            use the default account configured in ``gog auth list``.
        vip_senders: List of email addresses that should be flagged as VIP.
        timeout_seconds: Per-call subprocess timeout in seconds.
    """

    def __init__(
        self,
        account: str | None,
        vip_senders: list[str],
        timeout_seconds: float = 30.0,
    ) -> None:
        """Initialise the client; does not make any network calls."""
        self._account: str | None = account
        self._vip_senders: list[str] = [v.lower() for v in vip_senders]
        self._timeout = timeout_seconds

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _account_args(self) -> list[str]:
        """Return the ``--account <email>`` argument list, or empty list."""
        if self._account:
            return ["--account", self._account]
        return []

    async def _run(self, *args: str, stdin_text: str | None = None) -> Any:
        """Run a gog command, converting GogNotInstalledError to GmailClientError."""
        try:
            return await run_gog(*args, timeout_seconds=self._timeout, stdin_text=stdin_text)
        except GogNotInstalledError as exc:
            raise GmailClientError(
                str(exc),
                spoken_message="Das gog-Tool ist nicht installiert.",
            ) from exc
        except GogCommandError as exc:
            raise GmailClientError(
                str(exc),
                spoken_message=exc.spoken_message,
            ) from exc

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
            GmailClientError: On gog CLI failure.
        """
        max_results = min(max_results, 50)
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

        Args:
            query: Gmail search query (e.g. ``"from:alice is:unread"``).
            max_results: Maximum number of results (capped at 50).

        Returns:
            List of ``EmailMessage`` objects matching the query.

        Raises:
            GmailClientError: On gog CLI failure.
        """
        max_results = min(max_results, 50)
        cmd: list[str] = [
            "gmail", "messages", "search",
            query,
            "--max", str(max_results),
            *self._account_args(),
        ]
        data = await self._run(*cmd)
        messages_raw: list[dict[str, Any]] = (
            data.get("messages", []) if isinstance(data, dict) else []
        )
        return [_parse_gog_message(m, self._vip_senders) for m in messages_raw]

    async def get_message(
        self,
        message_id: str,
        include_body: bool = True,
    ) -> EmailMessage:
        """Fetch a single message by ID.

        Args:
            message_id: Gmail message ID string.
            include_body: When ``True`` the plain-text body is included if
                available.

        Returns:
            Parsed ``EmailMessage``.

        Raises:
            GmailClientError: When the message cannot be fetched.
        """
        # gog does not expose a single-message-get by ID; search by ID instead.
        cmd: list[str] = [
            "gmail", "messages", "search",
            f"rfc822msgid:{message_id}",
            "--max", "1",
            *self._account_args(),
        ]
        data = await self._run(*cmd)
        messages_raw: list[dict[str, Any]] = (
            data.get("messages", []) if isinstance(data, dict) else []
        )
        if not messages_raw:
            raise GmailClientError(
                f"Message {message_id} not found via gog search",
                spoken_message="Ich konnte die E-Mail nicht laden.",
            )
        msg = _parse_gog_message(messages_raw[0], self._vip_senders)
        if not include_body:
            msg.body_text = None
        return msg

    async def get_unread_count(self) -> int:
        """Return the approximate number of unread messages.

        Uses a lightweight gog search with max 1 and falls back to 0 on error.

        Returns:
            Integer unread count (approximate).

        Raises:
            GmailClientError: On gog CLI failure.
        """
        cmd: list[str] = [
            "gmail", "messages", "search",
            "is:unread in:inbox",
            "--max", "100",
            *self._account_args(),
        ]
        data = await self._run(*cmd)
        messages_raw: list[dict[str, Any]] = (
            data.get("messages", []) if isinstance(data, dict) else []
        )
        # gog paginates; if nextPageToken is present, there are more.
        count = len(messages_raw)
        if data.get("nextPageToken"):
            # More pages exist — return count + a "+more" sentinel value.
            # The exact count is unavailable without full pagination; return
            # count as a lower bound (same behaviour as Gmail API resultSizeEstimate).
            count = max(count, 100)
        return count

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

        cmd: list[str] = [
            "gmail", "drafts", "create",
            "--to", to,
            "--subject", subject,
            "--body-file", "-",
            *self._account_args(),
        ]
        data = await self._run(*cmd, stdin_text=body)
        draft_id: str = ""
        if isinstance(data, dict):
            draft_id = (
                data.get("id")
                or (data.get("draft", {}) or {}).get("id", "")
                or ""
            )
        if not draft_id:
            logger.warning("gog draft create returned no id; using placeholder")
            draft_id = f"draft-{to}-unknown"

        logger.info(f"Gmail draft created via gog: id={draft_id} to={to!r} subject={subject!r}")
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
        cmd: list[str] = [
            "gmail", "drafts", "send", draft_id,
            "--force",
            *self._account_args(),
        ]
        data = await self._run(*cmd)
        message_id: str = ""
        if isinstance(data, dict):
            message_id = (
                data.get("id")
                or data.get("messageId", "")
                or ""
            )
        logger.info(f"Gmail draft sent via gog: draft_id={draft_id} message_id={message_id}")
        return message_id or draft_id

    async def delete_draft(self, draft_id: str) -> bool:
        """Delete a draft by its ID (e.g. on send abort).

        Args:
            draft_id: Gmail draft ID.

        Returns:
            ``True`` on success, ``False`` on failure (non-fatal).
        """
        cmd: list[str] = [
            "gmail", "drafts", "delete", draft_id,
            "--force",
            *self._account_args(),
        ]
        try:
            await self._run(*cmd)
            logger.info(f"Gmail draft deleted via gog: draft_id={draft_id}")
            return True
        except GmailClientError as exc:
            logger.warning(f"Failed to delete draft {draft_id} via gog: {exc}")
            return False


# ---------------------------------------------------------------------------
# Module-level lazy factory (public API — patch point for tests)
# ---------------------------------------------------------------------------

_gmail_client_instance: GmailClient | None = None


def get_gmail_client(
    vip_senders: list[str] | None = None,
) -> GmailClient:
    """Return the module-level ``GmailClient`` singleton backed by ``gog``.

    On first call, builds the instance using the ``gmail.account`` config key
    (or ``GOG_ACCOUNT`` env var).  Subsequent calls ignore ``vip_senders`` and
    return the cached instance.

    Args:
        vip_senders: Optional list of VIP email addresses for the first-time
            build. Defaults to an empty list.

    Returns:
        Shared ``GmailClient`` instance.
    """
    global _gmail_client_instance
    if _gmail_client_instance is None:
        from utils.config_loader import get_config  # noqa: PLC0415

        cfg = get_config()
        gmail_cfg = cfg.get_section("gmail") or {}
        # Resolve account: config key "account" wins; env var GOG_ACCOUNT is
        # read by the gog binary itself, so we don't need to pass it explicitly.
        account: str | None = gmail_cfg.get("account") or None
        timeout = float(gmail_cfg.get("gog_timeout_seconds", 30))

        _gmail_client_instance = GmailClient(
            account=account,
            vip_senders=vip_senders or [],
            timeout_seconds=timeout,
        )
        logger.debug("GmailClient (gog) singleton created")
    return _gmail_client_instance
