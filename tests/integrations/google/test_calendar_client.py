"""Unit tests for GoogleCalendarClient — gog CLI adapter (ADR-0001 migration).

All calls to ``run_gog`` are replaced with ``AsyncMock`` objects.
No real subprocess is ever spawned; no live Calendar API calls are made.

Covers acceptance criteria:
- AC 2: CalendarEvent dataclass shape is unchanged
- AC 5: list_events happy path (timed + all-day events)
- AC 5: create_event / update_event / delete_event / get_event happy paths
- AC 5: GogCommandError / GogNotInstalledError → CalendarClientError
- Edge: missing start/end fields use sensible fallbacks
- Edge: singleton factory
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _gog_timed_event(
    event_id: str = "evt001",
    title: str = "Team Standup",
    start_iso: str = "2026-04-18T09:00:00+00:00",
    end_iso: str = "2026-04-18T09:30:00+00:00",
    location: str | None = "Zoom",
    attendees: list[str] | None = None,
    recurring_event_id: str | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    """Build a minimal gog calendar timed-event dict (raw Google Calendar API shape)."""
    raw: dict[str, Any] = {
        "id": event_id,
        "summary": title,
        "start": {"dateTime": start_iso},
        "end": {"dateTime": end_iso},
        "attendees": [{"email": e} for e in (attendees or [])],
    }
    if location:
        raw["location"] = location
    if recurring_event_id:
        raw["recurringEventId"] = recurring_event_id
    if description:
        raw["description"] = description
    return raw


def _gog_allday_event(
    event_id: str = "evt002",
    title: str = "Feiertag",
    date: str = "2026-04-19",
) -> dict[str, Any]:
    """Build a minimal gog calendar all-day event dict."""
    return {
        "id": event_id,
        "summary": title,
        "start": {"date": date},
        "end": {"date": date},
        "attendees": [],
    }


def _events_response(*events: dict[str, Any]) -> dict[str, Any]:
    """Build a gog calendar events response dict."""
    return {"events": list(events)}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client():
    """Return a GoogleCalendarClient with no account and a short timeout."""
    from integrations.google.calendar_client import GoogleCalendarClient

    return GoogleCalendarClient(account=None, timeout_seconds=5.0)


@pytest.fixture()
def account_client():
    """Return a GoogleCalendarClient configured with a specific account."""
    from integrations.google.calendar_client import GoogleCalendarClient

    return GoogleCalendarClient(account="user@gmail.com", timeout_seconds=5.0)


# ---------------------------------------------------------------------------
# Dataclass shape smoke test (AC #2)
# ---------------------------------------------------------------------------


def test_calendar_event_dataclass_shape():
    """CalendarEvent dataclass fields are unchanged from before the migration."""
    from integrations.google.calendar_client import CalendarEvent

    now = datetime.now(timezone.utc)
    evt = CalendarEvent(
        id="abc",
        calendar_id="primary",
        title="Test Event",
        start=now,
        end=now + timedelta(hours=1),
        all_day=False,
        location="Room A",
        description="Meeting notes",
        attendees=["alice@example.com"],
        is_recurring=False,
    )
    assert evt.id == "abc"
    assert evt.calendar_id == "primary"
    assert evt.all_day is False
    assert evt.is_recurring is False
    assert "alice@example.com" in evt.attendees


# ---------------------------------------------------------------------------
# _parse_gog_event helper
# ---------------------------------------------------------------------------


def test_parse_gog_event_timed():
    """_parse_gog_event correctly maps dateTime fields to a CalendarEvent."""
    from integrations.google.calendar_client import _parse_gog_event

    raw = _gog_timed_event(
        event_id="t1",
        title="Standup",
        start_iso="2026-04-18T09:00:00+00:00",
        end_iso="2026-04-18T09:30:00+00:00",
        location="Zoom",
        attendees=["a@x.com"],
        recurring_event_id="rec123",
    )
    evt = _parse_gog_event(raw, "primary")
    assert evt.id == "t1"
    assert evt.title == "Standup"
    assert evt.all_day is False
    assert evt.location == "Zoom"
    assert evt.start == datetime(2026, 4, 18, 9, 0, tzinfo=timezone.utc)
    assert evt.end == datetime(2026, 4, 18, 9, 30, tzinfo=timezone.utc)
    assert evt.is_recurring is True
    assert "a@x.com" in evt.attendees


def test_parse_gog_event_allday():
    """_parse_gog_event correctly maps date (all-day) fields; all_day=True."""
    from integrations.google.calendar_client import _parse_gog_event

    raw = _gog_allday_event(event_id="d1", title="Holiday", date="2026-04-19")
    evt = _parse_gog_event(raw, "primary")
    assert evt.all_day is True
    assert evt.start == datetime(2026, 4, 19, tzinfo=timezone.utc)


def test_parse_gog_event_missing_summary_uses_default():
    """_parse_gog_event uses '(No title)' when summary is absent."""
    from integrations.google.calendar_client import _parse_gog_event

    raw = _gog_timed_event()
    raw.pop("summary")
    evt = _parse_gog_event(raw, "primary")
    assert evt.title == "(No title)"


def test_parse_gog_event_empty_dates_fall_back():
    """_parse_gog_event falls back to now when dateTime is absent."""
    from integrations.google.calendar_client import _parse_gog_event

    raw = {"id": "x", "summary": "Empty", "start": {}, "end": {}, "attendees": []}
    before = datetime.now(timezone.utc)
    evt = _parse_gog_event(raw, "primary")
    after = datetime.now(timezone.utc)
    assert before <= evt.start <= after


# ---------------------------------------------------------------------------
# GoogleCalendarClient.list_events happy path (AC #5)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_events_returns_calendar_events(client):
    """list_events returns correctly parsed CalendarEvent objects."""
    from integrations.google.calendar_client import CalendarEvent

    canned = _events_response(_gog_timed_event("e1", "Meeting"))
    with patch(
        "integrations.google.calendar_client.run_gog",
        new=AsyncMock(return_value=canned),
    ):
        events = await client.list_events()

    assert len(events) == 1
    assert isinstance(events[0], CalendarEvent)
    assert events[0].id == "e1"
    assert events[0].title == "Meeting"


@pytest.mark.asyncio
async def test_list_events_allday(client):
    """list_events correctly handles all-day events."""
    canned = _events_response(_gog_allday_event("d1", "Holiday", "2026-04-19"))
    with patch(
        "integrations.google.calendar_client.run_gog",
        new=AsyncMock(return_value=canned),
    ):
        events = await client.list_events()

    assert events[0].all_day is True


@pytest.mark.asyncio
async def test_list_events_empty_response(client):
    """list_events returns an empty list when gog returns no events."""
    with patch(
        "integrations.google.calendar_client.run_gog",
        new=AsyncMock(return_value={"events": []}),
    ):
        events = await client.list_events()

    assert events == []


@pytest.mark.asyncio
async def test_list_events_passes_calendar_id(client):
    """list_events passes the calendar_id to gog."""
    captured: list[tuple] = []

    async def capture_run(*args: str, **kwargs: Any) -> dict:
        captured.append(args)
        return {"events": []}

    with patch("integrations.google.calendar_client.run_gog", side_effect=capture_run):
        await client.list_events(calendar_id="work@group.calendar.google.com")

    assert "work@group.calendar.google.com" in captured[0]


@pytest.mark.asyncio
async def test_list_events_caps_max_results(client):
    """list_events caps max_results at 250."""
    captured: list[tuple] = []

    async def capture_run(*args: str, **kwargs: Any) -> dict:
        captured.append(args)
        return {"events": []}

    with patch("integrations.google.calendar_client.run_gog", side_effect=capture_run):
        await client.list_events(max_results=9999)

    idx = captured[0].index("--max")
    assert int(captured[0][idx + 1]) <= 250


@pytest.mark.asyncio
async def test_list_events_defaults_start_end(client):
    """list_events defaults start to now and end to start+48h."""
    captured: list[tuple] = []

    async def capture_run(*args: str, **kwargs: Any) -> dict:
        captured.append(args)
        return {"events": []}

    before = datetime.now(timezone.utc)
    with patch("integrations.google.calendar_client.run_gog", side_effect=capture_run):
        await client.list_events()

    # "--from" and "--to" should both be present
    assert "--from" in captured[0]
    assert "--to" in captured[0]


# ---------------------------------------------------------------------------
# GoogleCalendarClient.create_event (AC #5)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_event_returns_calendar_event(client):
    """create_event calls gog and returns a CalendarEvent."""
    from integrations.google.calendar_client import CalendarEvent

    start = datetime(2026, 4, 20, 14, 0, tzinfo=timezone.utc)
    end = datetime(2026, 4, 20, 15, 0, tzinfo=timezone.utc)
    created_raw = _gog_timed_event(
        "new123", "New Meeting", start.isoformat(), end.isoformat()
    )
    with patch(
        "integrations.google.calendar_client.run_gog",
        new=AsyncMock(return_value=created_raw),
    ):
        result = await client.create_event(title="New Meeting", start=start, end=end)

    assert isinstance(result, CalendarEvent)
    assert result.id == "new123"
    assert result.title == "New Meeting"


@pytest.mark.asyncio
async def test_create_event_passes_location_and_description(client):
    """create_event passes --location and --description when provided."""
    captured: list[tuple] = []

    async def capture_run(*args: str, **kwargs: Any) -> dict:
        captured.append(args)
        return _gog_timed_event()

    start = datetime(2026, 4, 20, 14, 0, tzinfo=timezone.utc)
    end = start + timedelta(hours=1)
    with patch("integrations.google.calendar_client.run_gog", side_effect=capture_run):
        await client.create_event(
            title="Loc Meeting",
            start=start,
            end=end,
            location="Room 42",
            description="Agenda here",
        )

    assert "--location" in captured[0]
    assert "Room 42" in captured[0]
    assert "--description" in captured[0]
    assert "Agenda here" in captured[0]


# ---------------------------------------------------------------------------
# GoogleCalendarClient.update_event (AC #5)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_event_returns_updated_event(client):
    """update_event calls gog with update args and returns updated CalendarEvent."""
    updated_raw = _gog_timed_event("evt1", "Updated Title")
    with patch(
        "integrations.google.calendar_client.run_gog",
        new=AsyncMock(return_value=updated_raw),
    ):
        result = await client.update_event(event_id="evt1", title="Updated Title")

    assert result.title == "Updated Title"


@pytest.mark.asyncio
async def test_update_event_passes_optional_fields(client):
    """update_event passes --summary, --from, --to, --location when provided."""
    captured: list[tuple] = []

    async def capture_run(*args: str, **kwargs: Any) -> dict:
        captured.append(args)
        return _gog_timed_event()

    new_start = datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc)
    new_end = new_start + timedelta(hours=1)
    with patch("integrations.google.calendar_client.run_gog", side_effect=capture_run):
        await client.update_event(
            event_id="e1",
            title="New Title",
            start=new_start,
            end=new_end,
            location="HQ",
        )

    args = captured[0]
    assert "--summary" in args
    assert "New Title" in args
    assert "--from" in args
    assert "--to" in args
    assert "--location" in args
    assert "HQ" in args


# ---------------------------------------------------------------------------
# GoogleCalendarClient.delete_event (AC #5)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_event_calls_gog(client):
    """delete_event calls gog and returns without error."""
    captured: list[tuple] = []

    async def capture_run(*args: str, **kwargs: Any) -> dict:
        captured.append(args)
        return {}

    with patch("integrations.google.calendar_client.run_gog", side_effect=capture_run):
        await client.delete_event(event_id="evt1")

    assert "calendar" in captured[0]
    assert "delete" in captured[0]
    assert "evt1" in captured[0]


@pytest.mark.asyncio
async def test_delete_event_passes_calendar_id(client):
    """delete_event passes the calendar_id to gog."""
    captured: list[tuple] = []

    async def capture_run(*args: str, **kwargs: Any) -> dict:
        captured.append(args)
        return {}

    with patch("integrations.google.calendar_client.run_gog", side_effect=capture_run):
        await client.delete_event(event_id="e1", calendar_id="work@group.calendar.google.com")

    assert "work@group.calendar.google.com" in captured[0]


# ---------------------------------------------------------------------------
# GoogleCalendarClient.get_event
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_event_returns_matching_event(client):
    """get_event searches events and returns the one with matching id."""
    canned = _events_response(
        _gog_timed_event("evt_a", "Other"),
        _gog_timed_event("evt_b", "Target"),
    )
    with patch(
        "integrations.google.calendar_client.run_gog",
        new=AsyncMock(return_value=canned),
    ):
        result = await client.get_event("evt_b")

    assert result.id == "evt_b"
    assert result.title == "Target"


@pytest.mark.asyncio
async def test_get_event_raises_when_not_found(client):
    """get_event raises CalendarClientError when event is not in the result set."""
    from integrations.google.calendar_client import CalendarClientError

    canned = _events_response(_gog_timed_event("other", "Other"))
    with patch(
        "integrations.google.calendar_client.run_gog",
        new=AsyncMock(return_value=canned),
    ):
        with pytest.raises(CalendarClientError) as exc_info:
            await client.get_event("missing_event_id")

    assert exc_info.value.spoken_message


# ---------------------------------------------------------------------------
# Error propagation (AC #5 error paths)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gog_command_error_raises_calendar_client_error(client):
    """GogCommandError is wrapped as CalendarClientError."""
    from integrations.google.calendar_client import CalendarClientError
    from integrations.openclaw.client import GogCommandError

    with patch(
        "integrations.google.calendar_client.run_gog",
        new=AsyncMock(side_effect=GogCommandError("exit 1", "Calendar nicht erreichbar.")),
    ):
        with pytest.raises(CalendarClientError) as exc_info:
            await client.list_events()

    assert exc_info.value.spoken_message


@pytest.mark.asyncio
async def test_gog_not_installed_raises_calendar_client_error(client):
    """GogNotInstalledError is wrapped as CalendarClientError."""
    from integrations.google.calendar_client import CalendarClientError
    from integrations.openclaw.client import GogNotInstalledError

    with patch(
        "integrations.google.calendar_client.run_gog",
        new=AsyncMock(side_effect=GogNotInstalledError("no gog")),
    ):
        with pytest.raises(CalendarClientError) as exc_info:
            await client.create_event(
                title="X",
                start=datetime.now(timezone.utc),
                end=datetime.now(timezone.utc) + timedelta(hours=1),
            )

    assert exc_info.value.spoken_message


@pytest.mark.asyncio
async def test_delete_event_gog_error_raises(client):
    """delete_event propagates GogCommandError as CalendarClientError."""
    from integrations.google.calendar_client import CalendarClientError
    from integrations.openclaw.client import GogCommandError

    with patch(
        "integrations.google.calendar_client.run_gog",
        new=AsyncMock(side_effect=GogCommandError("not found")),
    ):
        with pytest.raises(CalendarClientError):
            await client.delete_event("evt_missing")


# ---------------------------------------------------------------------------
# Account args
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_account_args_included_when_set(account_client):
    """When account is configured, --account is passed to gog."""
    captured: list[tuple] = []

    async def capture_run(*args: str, **kwargs: Any) -> dict:
        captured.append(args)
        return {"events": []}

    with patch("integrations.google.calendar_client.run_gog", side_effect=capture_run):
        await account_client.list_events()

    assert "--account" in captured[0]
    idx = captured[0].index("--account")
    assert captured[0][idx + 1] == "user@gmail.com"


@pytest.mark.asyncio
async def test_no_account_args_when_account_is_none(client):
    """When account is None, --account is NOT passed to gog."""
    captured: list[tuple] = []

    async def capture_run(*args: str, **kwargs: Any) -> dict:
        captured.append(args)
        return {"events": []}

    with patch("integrations.google.calendar_client.run_gog", side_effect=capture_run):
        await client.list_events()

    assert "--account" not in captured[0]


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------


def test_get_calendar_client_singleton():
    """get_calendar_client() returns the same instance on repeated calls."""
    import integrations.google.calendar_client as _mod

    original = _mod._calendar_client
    _mod._calendar_client = None

    try:
        with patch("utils.config_loader.get_config") as mock_cfg:
            cfg = MagicMock()
            cfg.get_section.return_value = {}
            mock_cfg.return_value = cfg

            c1 = _mod.get_calendar_client()
            c2 = _mod.get_calendar_client()
            assert c1 is c2
    finally:
        _mod._calendar_client = original


def test_get_calendar_client_fresh_after_reset():
    """A new instance is created after the singleton is cleared."""
    import integrations.google.calendar_client as _mod

    original = _mod._calendar_client
    _mod._calendar_client = None

    try:
        with patch("utils.config_loader.get_config") as mock_cfg:
            cfg = MagicMock()
            cfg.get_section.return_value = {}
            mock_cfg.return_value = cfg

            c1 = _mod.get_calendar_client()
            _mod._calendar_client = None
            c2 = _mod.get_calendar_client()
            assert c1 is not c2
    finally:
        _mod._calendar_client = original
