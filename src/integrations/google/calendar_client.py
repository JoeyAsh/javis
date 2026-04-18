"""Google Calendar API client for JARVIS.

Wraps the Google Calendar REST API via ``googleapiclient``. All blocking
API calls are executed through ``asyncio.to_thread`` so the event loop is
never stalled. Natural-language date parsing is handled by ``dateparser``.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import googleapiclient.discovery

from utils.logger import get_logger

logger = get_logger("calendar_client")

# ---------------------------------------------------------------------------
# OAuth scopes
# ---------------------------------------------------------------------------

CALENDAR_SCOPES: list[str] = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
]


# ---------------------------------------------------------------------------
# Data classes
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
# Exceptions
# ---------------------------------------------------------------------------


class CalendarClientError(Exception):
    """Raised when a Calendar API call fails in an anticipated way."""

    def __init__(self, message: str, spoken_message: str = "") -> None:
        """Initialise with a technical message and an optional TTS-friendly fallback."""
        super().__init__(message)
        self.spoken_message: str = spoken_message or message


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_google_datetime(value: str | None) -> datetime | None:
    """Parse a Google Calendar dateTime string (ISO 8601 with offset) to UTC datetime."""
    if not value:
        return None
    # Remove the 'Z' suffix and treat as UTC, or parse offset
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def _parse_google_date(value: str | None) -> datetime | None:
    """Parse a Google Calendar all-day date string (YYYY-MM-DD) to a UTC midnight datetime."""
    if not value:
        return None
    date = datetime.strptime(value, "%Y-%m-%d")
    return date.replace(tzinfo=timezone.utc)


def _parse_event(raw: dict[str, Any], calendar_id: str) -> CalendarEvent:
    """Convert a raw Google Calendar API event dict to a ``CalendarEvent``.

    Handles both timed (``dateTime``) and all-day (``date``) event formats.
    """
    event_id: str = raw.get("id", "")
    title: str = raw.get("summary", "(No title)")

    start_obj: dict[str, Any] = raw.get("start", {})
    end_obj: dict[str, Any] = raw.get("end", {})

    all_day = "date" in start_obj and "dateTime" not in start_obj

    if all_day:
        start_dt = _parse_google_date(start_obj.get("date")) or datetime.now(timezone.utc)
        end_dt = _parse_google_date(end_obj.get("date")) or start_dt + timedelta(days=1)
    else:
        start_dt = _parse_google_datetime(start_obj.get("dateTime")) or datetime.now(timezone.utc)
        end_dt = _parse_google_datetime(end_obj.get("dateTime")) or start_dt + timedelta(hours=1)

    location: str | None = raw.get("location") or None
    description: str | None = raw.get("description") or None

    attendees_raw: list[dict[str, Any]] = raw.get("attendees", [])
    attendees: list[str] = [
        a.get("email", "") for a in attendees_raw if a.get("email")
    ]

    is_recurring: bool = bool(raw.get("recurringEventId"))

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


def _event_to_body(
    title: str,
    start: datetime,
    end: datetime,
    location: str | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    """Build a Google Calendar API event resource body."""
    body: dict[str, Any] = {
        "summary": title,
        "start": {"dateTime": start.isoformat(), "timeZone": "UTC"},
        "end": {"dateTime": end.isoformat(), "timeZone": "UTC"},
    }
    if location:
        body["location"] = location
    if description:
        body["description"] = description
    return body


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class GoogleCalendarClient:
    """Google Calendar API client — lazy-initialised, thread-safe."""

    def __init__(self, oauth_service: Any) -> None:
        """Initialise with a ``GoogleOAuthService`` instance.

        Args:
            oauth_service: Shared ``GoogleOAuthService`` used to build the
                ``calendar`` API service object on first use.
        """
        self._oauth_service = oauth_service
        self._service: Any = None
        self._lock: asyncio.Lock = asyncio.Lock()

    async def _get_service(self) -> Any:
        """Return a lazy-initialised Google Calendar API service object.

        Thread-safe via ``asyncio.Lock``. The service is built once and
        reused for all subsequent calls.
        """
        async with self._lock:
            if self._service is None:
                self._service = await asyncio.to_thread(
                    self._oauth_service.build_service,
                    "calendar",
                    "v3",
                    scopes=CALENDAR_SCOPES,
                )
        return self._service

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
        """
        if start is None:
            start = datetime.now(timezone.utc)
        if end is None:
            end = start + timedelta(hours=48)

        time_min = start.isoformat()
        time_max = end.isoformat()

        try:
            service = await self._get_service()

            def _call() -> dict[str, Any]:
                return (
                    service.events()
                    .list(
                        calendarId=calendar_id,
                        timeMin=time_min,
                        timeMax=time_max,
                        maxResults=min(max_results, 250),
                        singleEvents=True,
                        orderBy="startTime",
                    )
                    .execute()
                )

            result: dict[str, Any] = await asyncio.to_thread(_call)
            items: list[dict[str, Any]] = result.get("items", [])
            return [_parse_event(item, calendar_id) for item in items]

        except CalendarClientError:
            raise
        except Exception as exc:
            _handle_api_exception(exc, "list_events")
            return []  # unreachable — _handle_api_exception always raises

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
        """
        body = _event_to_body(title, start, end, location, description)
        try:
            service = await self._get_service()

            def _call() -> dict[str, Any]:
                return (
                    service.events()
                    .insert(calendarId=calendar_id, body=body)
                    .execute()
                )

            raw: dict[str, Any] = await asyncio.to_thread(_call)
            logger.info(f"Calendar event created: id={raw.get('id')!r} title={title!r}")
            return _parse_event(raw, calendar_id)

        except CalendarClientError:
            raise
        except Exception as exc:
            _handle_api_exception(exc, "create_event")
            raise  # satisfy mypy — _handle_api_exception always raises

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

        Fetches the current event, applies the supplied overrides, then
        writes back via ``events().update()``.

        Args:
            event_id: Google Calendar event identifier.
            calendar_id: Target calendar (default ``"primary"``).
            title: New title if changing.
            start: New start datetime if changing.
            end: New end datetime if changing.
            location: New location if changing.

        Returns:
            The updated ``CalendarEvent``.
        """
        try:
            service = await self._get_service()

            def _get() -> dict[str, Any]:
                return (
                    service.events()
                    .get(calendarId=calendar_id, eventId=event_id)
                    .execute()
                )

            raw: dict[str, Any] = await asyncio.to_thread(_get)

            # Apply overrides
            if title is not None:
                raw["summary"] = title
            if start is not None:
                raw["start"] = {"dateTime": start.isoformat(), "timeZone": "UTC"}
            if end is not None:
                raw["end"] = {"dateTime": end.isoformat(), "timeZone": "UTC"}
            if location is not None:
                raw["location"] = location

            def _update() -> dict[str, Any]:
                return (
                    service.events()
                    .update(calendarId=calendar_id, eventId=event_id, body=raw)
                    .execute()
                )

            updated: dict[str, Any] = await asyncio.to_thread(_update)
            logger.info(f"Calendar event updated: id={event_id!r}")
            return _parse_event(updated, calendar_id)

        except CalendarClientError:
            raise
        except Exception as exc:
            _handle_api_exception(exc, "update_event")
            raise  # satisfy mypy

    async def delete_event(
        self,
        event_id: str,
        calendar_id: str = "primary",
    ) -> None:
        """Delete an event from the calendar.

        Args:
            event_id: Google Calendar event identifier.
            calendar_id: Target calendar (default ``"primary"``).
        """
        try:
            service = await self._get_service()

            def _call() -> None:
                service.events().delete(
                    calendarId=calendar_id, eventId=event_id
                ).execute()

            await asyncio.to_thread(_call)
            logger.info(f"Calendar event deleted: id={event_id!r}")

        except CalendarClientError:
            raise
        except Exception as exc:
            _handle_api_exception(exc, "delete_event")

    async def get_event(
        self,
        event_id: str,
        calendar_id: str = "primary",
    ) -> CalendarEvent:
        """Fetch a single event by ID.

        Args:
            event_id: Google Calendar event identifier.
            calendar_id: Target calendar (default ``"primary"``).

        Returns:
            The matching ``CalendarEvent``.
        """
        try:
            service = await self._get_service()

            def _call() -> dict[str, Any]:
                return (
                    service.events()
                    .get(calendarId=calendar_id, eventId=event_id)
                    .execute()
                )

            raw: dict[str, Any] = await asyncio.to_thread(_call)
            return _parse_event(raw, calendar_id)

        except CalendarClientError:
            raise
        except Exception as exc:
            _handle_api_exception(exc, "get_event")
            raise  # satisfy mypy


def _handle_api_exception(exc: Exception, operation: str) -> None:
    """Convert a ``googleapiclient`` HTTP error to a ``CalendarClientError``.

    Raises:
        CalendarClientError: Always — wraps the original exception with
            a user-facing spoken message appropriate to the HTTP status.
    """
    # Try to extract HTTP status from googleapiclient HttpError
    status: int | None = None
    try:
        status = exc.resp.status  # type: ignore[attr-defined]
    except AttributeError:
        pass

    if status == 401 or status == 403:
        raise CalendarClientError(
            f"Calendar API {operation} unauthorised ({status}): {exc}",
            spoken_message=(
                "Calendar access is not authorized. Please re-authenticate."
            ),
        ) from exc
    if status == 404:
        raise CalendarClientError(
            f"Calendar API {operation} not found (404): {exc}",
            spoken_message=(
                "I couldn't find that event. It may have already been removed."
            ),
        ) from exc
    raise CalendarClientError(
        f"Calendar API {operation} failed: {exc}",
        spoken_message="There was a problem accessing your calendar. Please try again.",
    ) from exc


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_calendar_client: GoogleCalendarClient | None = None


def get_calendar_client() -> GoogleCalendarClient:
    """Return the module-level ``GoogleCalendarClient`` singleton.

    Constructs the client on first call using the shared
    ``GoogleOAuthService``. Subsequent calls return the same instance.
    """
    global _calendar_client
    if _calendar_client is None:
        from integrations.google.oauth import get_google_oauth_service  # noqa: PLC0415

        oauth_service = get_google_oauth_service()
        _calendar_client = GoogleCalendarClient(oauth_service)
    return _calendar_client
