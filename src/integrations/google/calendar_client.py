"""Google Calendar adapter for JARVIS — thin OpenClaw/gog shim (ADR-0001).

All Google Calendar API calls are delegated to the ``gog`` CLI binary.
No ``googleapiclient`` or ``google-auth`` imports remain in this module.

Public surface (dataclasses, exception type, factory function) is 100%
backwards-compatible with the previous googleapiclient implementation so
``ws_server.py``, ``orchestrator.py``, and test mocks continue to work
unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from integrations.openclaw.client import GogCommandError, GogNotInstalledError, run_gog
from utils.logger import get_logger

logger = get_logger("calendar_client")


# ---------------------------------------------------------------------------
# Data classes (public surface — must stay backwards-compatible)
# ---------------------------------------------------------------------------


@dataclass
class CalendarEvent:
    """A single Google Calendar event with parsed fields."""

    id: str
    calendar_id: str
    title: str
    start: datetime
    end: datetime
    all_day: bool
    location: str | None
    description: str | None
    attendees: list[str]
    is_recurring: bool


# ---------------------------------------------------------------------------
# Exception (kept for caller compatibility)
# ---------------------------------------------------------------------------


class CalendarClientError(Exception):
    """Raised when a Calendar operation fails in an anticipated way."""

    def __init__(self, message: str, spoken_message: str = "") -> None:
        """Initialise with a technical message and an optional TTS-friendly fallback."""
        super().__init__(message)
        self.spoken_message: str = spoken_message or message


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_iso_dt(value: str | None, fallback: datetime | None = None) -> datetime:
    """Parse an ISO 8601 string (possibly with trailing Z) to a UTC-aware datetime."""
    _fb = fallback or datetime.now(timezone.utc)
    if not value:
        return _fb
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return _fb


def _parse_gog_event(raw: dict[str, Any], calendar_id: str) -> CalendarEvent:
    """Convert a ``gog calendar events --json`` event dict to a ``CalendarEvent``.

    ``gog`` returns the raw Google Calendar API JSON object, so the shape is::

        {
          "id": "...",
          "summary": "...",
          "start": {"dateTime": "...", "timeZone": "..."},
          "end":   {"dateTime": "...", "timeZone": "..."},
          "location": "...",
          "description": "...",
          "attendees": [{"email": "..."}, ...],
          "recurringEventId": "..."
        }

    All-day events use ``start.date`` instead of ``start.dateTime``.
    """
    event_id: str = raw.get("id", "")
    title: str = raw.get("summary", "(No title)")

    start_obj: dict[str, Any] = raw.get("start", {})
    end_obj: dict[str, Any] = raw.get("end", {})

    all_day = "date" in start_obj and "dateTime" not in start_obj

    now_utc = datetime.now(timezone.utc)

    if all_day:
        date_str: str = start_obj.get("date", "")
        try:
            start_dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            start_dt = now_utc
        end_date_str: str = end_obj.get("date", "")
        try:
            end_dt = datetime.strptime(end_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            end_dt = start_dt + timedelta(days=1)
    else:
        start_dt = _parse_iso_dt(start_obj.get("dateTime"), now_utc)
        end_dt = _parse_iso_dt(end_obj.get("dateTime"), start_dt + timedelta(hours=1))

    location: str | None = raw.get("location") or None
    description: str | None = raw.get("description") or None

    attendees_raw: list[dict[str, Any]] = raw.get("attendees", [])
    attendees: list[str] = [
        a.get("email", "") for a in attendees_raw if a.get("email")
    ]

    is_recurring = bool(raw.get("recurringEventId"))

    return CalendarEvent(
        id=event_id,
        calendar_id=calendar_id,
        title=title,
        start=start_dt,
        end=end_dt,
        all_day=all_day,
        location=location,
        description=description,
        attendees=attendees,
        is_recurring=is_recurring,
    )


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class GoogleCalendarClient:
    """Async Google Calendar adapter backed by the ``gog`` CLI binary.

    All network I/O is async via ``asyncio.create_subprocess_exec``.  The
    public method surface is 100% compatible with the previous
    ``googleapiclient``-based implementation.

    Args:
        account: Google account email passed to ``gog --account``.  Omit to
            use the default account configured in ``gog auth list``.
        timeout_seconds: Per-call subprocess timeout in seconds.
    """

    def __init__(
        self,
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
        """Run a gog command, converting errors to CalendarClientError."""
        try:
            return await run_gog(*args, timeout_seconds=self._timeout)
        except GogNotInstalledError as exc:
            raise CalendarClientError(
                str(exc),
                spoken_message="Das gog-Tool ist nicht installiert.",
            ) from exc
        except GogCommandError as exc:
            raise CalendarClientError(
                str(exc),
                spoken_message=exc.spoken_message,
            ) from exc

    # ------------------------------------------------------------------
    # Public async API
    # ------------------------------------------------------------------

    async def list_events(
        self,
        calendar_id: str = "primary",
        start: datetime | None = None,
        end: datetime | None = None,
        max_results: int = 20,
    ) -> list[CalendarEvent]:
        """Fetch upcoming events from a Google Calendar.

        Args:
            calendar_id: Target calendar (default ``"primary"``).
            start: Window start; defaults to now if not provided.
            end: Window end; defaults to ``start + 48 h`` if not provided.
            max_results: Maximum events to return (hard cap 250).

        Returns:
            List of ``CalendarEvent`` objects sorted by start time.

        Raises:
            CalendarClientError: On gog CLI failure.
        """
        if start is None:
            start = datetime.now(timezone.utc)
        if end is None:
            end = start + timedelta(hours=48)

        cmd: list[str] = [
            "calendar", "events",
            calendar_id,
            "--from", start.isoformat(),
            "--to", end.isoformat(),
            "--max", str(min(max_results, 250)),
            *self._account_args(),
        ]
        data = await self._run(*cmd)
        events_raw: list[dict[str, Any]] = (
            data.get("events", []) if isinstance(data, dict) else []
        )
        return [_parse_gog_event(evt, calendar_id) for evt in events_raw]

    async def create_event(
        self,
        title: str,
        start: datetime,
        end: datetime,
        calendar_id: str = "primary",
        location: str | None = None,
        description: str | None = None,
    ) -> CalendarEvent:
        """Create a new event in the specified calendar.

        Args:
            title: Event title / summary.
            start: Event start datetime (timezone-aware).
            end: Event end datetime (timezone-aware).
            calendar_id: Target calendar (default ``"primary"``).
            location: Optional location string.
            description: Optional event description.

        Returns:
            The created ``CalendarEvent`` with server-assigned ``id``.

        Raises:
            CalendarClientError: On gog CLI failure.
        """
        cmd: list[str] = [
            "calendar", "create",
            calendar_id,
            "--summary", title,
            "--from", start.isoformat(),
            "--to", end.isoformat(),
            "--force",
            *self._account_args(),
        ]
        if location:
            cmd += ["--location", location]
        if description:
            cmd += ["--description", description]

        data = await self._run(*cmd)
        raw: dict[str, Any] = data if isinstance(data, dict) else {}
        evt = _parse_gog_event(raw, calendar_id)
        logger.info(f"Calendar event created via gog: id={evt.id!r} title={title!r}")
        return evt

    async def update_event(
        self,
        event_id: str,
        calendar_id: str = "primary",
        title: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        location: str | None = None,
    ) -> CalendarEvent:
        """Update fields on an existing event.

        Args:
            event_id: Google Calendar event identifier.
            calendar_id: Target calendar (default ``"primary"``).
            title: New title if changing.
            start: New start datetime if changing.
            end: New end datetime if changing.
            location: New location if changing.

        Returns:
            The updated ``CalendarEvent``.

        Raises:
            CalendarClientError: On gog CLI failure.
        """
        cmd: list[str] = [
            "calendar", "update",
            calendar_id,
            event_id,
            "--force",
            *self._account_args(),
        ]
        if title:
            cmd += ["--summary", title]
        if start:
            cmd += ["--from", start.isoformat()]
        if end:
            cmd += ["--to", end.isoformat()]
        if location:
            cmd += ["--location", location]

        data = await self._run(*cmd)
        raw: dict[str, Any] = data if isinstance(data, dict) else {}
        evt = _parse_gog_event(raw, calendar_id)
        logger.info(f"Calendar event updated via gog: id={event_id!r}")
        return evt

    async def delete_event(
        self,
        event_id: str,
        calendar_id: str = "primary",
    ) -> None:
        """Delete an event from the calendar.

        Args:
            event_id: Google Calendar event identifier.
            calendar_id: Target calendar (default ``"primary"``).

        Raises:
            CalendarClientError: On gog CLI failure.
        """
        cmd: list[str] = [
            "calendar", "delete",
            calendar_id, event_id,
            "--force",
            *self._account_args(),
        ]
        await self._run(*cmd)
        logger.info(f"Calendar event deleted via gog: id={event_id!r}")

    async def get_event(
        self,
        event_id: str,
        calendar_id: str = "primary",
    ) -> CalendarEvent:
        """Fetch a single event by ID.

        ``gog`` does not expose a direct get-by-id; list events and filter.

        Args:
            event_id: Google Calendar event identifier.
            calendar_id: Target calendar (default ``"primary"``).

        Returns:
            The matching ``CalendarEvent``.

        Raises:
            CalendarClientError: When the event cannot be found.
        """
        # Fetch a broad window and search for the event by id.
        now = datetime.now(timezone.utc)
        events = await self.list_events(
            calendar_id=calendar_id,
            start=now - timedelta(days=365),
            end=now + timedelta(days=365),
            max_results=250,
        )
        for evt in events:
            if evt.id == event_id:
                return evt
        raise CalendarClientError(
            f"Event {event_id} not found in calendar {calendar_id}",
            spoken_message="Ich konnte den Termin nicht finden.",
        )


# ---------------------------------------------------------------------------
# Module-level singleton factory (public API — patch point for tests)
# ---------------------------------------------------------------------------

_calendar_client: GoogleCalendarClient | None = None


def get_calendar_client() -> GoogleCalendarClient:
    """Return the module-level ``GoogleCalendarClient`` singleton backed by ``gog``.

    Constructs the client on first call using the ``calendar.account`` config key.
    Subsequent calls return the same instance.
    """
    global _calendar_client
    if _calendar_client is None:
        from utils.config_loader import get_config  # noqa: PLC0415

        cfg = get_config()
        cal_cfg = cfg.get_section("calendar") or {}
        account: str | None = cal_cfg.get("account") or None
        timeout = float(cal_cfg.get("gog_timeout_seconds", 30))
        _calendar_client = GoogleCalendarClient(account=account, timeout_seconds=timeout)
        logger.debug("GoogleCalendarClient (gog) singleton created")
    return _calendar_client
