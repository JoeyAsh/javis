"""Unit tests for GoogleCalendarClient.

All ``googleapiclient`` / ``GoogleOAuthService.build_service`` calls are
replaced with ``MagicMock`` objects.  No real OAuth flow or network call
is ever made.

Covers acceptance criteria 1–4 and 14.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_timed_event(
    event_id: str = "evt001",
    title: str = "Team Standup",
    start_iso: str = "2026-04-18T09:00:00+02:00",
    end_iso: str = "2026-04-18T09:30:00+02:00",
    location: str | None = "Zoom",
    attendees: list[str] | None = None,
    recurring_event_id: str | None = None,
) -> dict[str, Any]:
    """Build a minimal Google Calendar timed-event dict."""
    raw: dict[str, Any] = {
        "id": event_id,
        "summary": title,
        "start": {"dateTime": start_iso, "timeZone": "Europe/Berlin"},
        "end": {"dateTime": end_iso, "timeZone": "Europe/Berlin"},
        "attendees": [{"email": e} for e in (attendees or [])],
    }
    if location:
        raw["location"] = location
    if recurring_event_id:
        raw["recurringEventId"] = recurring_event_id
    return raw


def _make_allday_event(
    event_id: str = "evt002",
    title: str = "Feiertag",
    date: str = "2026-04-19",
) -> dict[str, Any]:
    """Build a minimal Google Calendar all-day event dict."""
    return {
        "id": event_id,
        "summary": title,
        "start": {"date": date},
        "end": {"date": date},
        "attendees": [],
    }


def _make_mock_service(
    list_response: dict[str, Any] | None = None,
    insert_response: dict[str, Any] | None = None,
    update_response: dict[str, Any] | None = None,
    get_response: dict[str, Any] | None = None,
) -> MagicMock:
    """Build a chainable MagicMock mimicking the Calendar service resource."""
    svc = MagicMock()

    # events().list().execute()
    svc.events.return_value.list.return_value.execute = MagicMock(
        return_value=list_response or {"items": []}
    )

    # events().insert().execute()
    svc.events.return_value.insert.return_value.execute = MagicMock(
        return_value=insert_response or _make_timed_event()
    )

    # events().update().execute()
    svc.events.return_value.update.return_value.execute = MagicMock(
        return_value=update_response or _make_timed_event()
    )

    # events().get().execute()
    svc.events.return_value.get.return_value.execute = MagicMock(
        return_value=get_response or _make_timed_event()
    )

    # events().delete().execute() → returns None
    svc.events.return_value.delete.return_value.execute = MagicMock(return_value=None)

    return svc


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def oauth_service() -> MagicMock:
    """Return a mock GoogleOAuthService."""
    svc = MagicMock()
    svc.build_service = MagicMock()
    return svc


@pytest.fixture()
def client(oauth_service: MagicMock):
    """Return a fresh GoogleCalendarClient with a mock oauth service."""
    from integrations.google.calendar_client import GoogleCalendarClient

    return GoogleCalendarClient(oauth_service=oauth_service)


# ---------------------------------------------------------------------------
# _get_service initialisation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_service_calls_build_service(
    client, oauth_service: MagicMock
) -> None:
    """_get_service calls oauth_service.build_service exactly once."""
    mock_svc = MagicMock()
    oauth_service.build_service.return_value = mock_svc

    svc1 = await client._get_service()
    svc2 = await client._get_service()

    assert svc1 is mock_svc
    assert svc2 is mock_svc
    oauth_service.build_service.assert_called_once()


# ---------------------------------------------------------------------------
# list_events — timed events
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_events_timed(client, oauth_service: MagicMock) -> None:
    """list_events correctly maps dateTime fields to CalendarEvent."""
    raw_evt = _make_timed_event(
        event_id="abc123",
        title="Standup",
        start_iso="2026-04-18T09:00:00+00:00",
        end_iso="2026-04-18T09:30:00+00:00",
        location="Zoom",
    )
    mock_svc = _make_mock_service(list_response={"items": [raw_evt]})
    oauth_service.build_service.return_value = mock_svc

    now = datetime(2026, 4, 18, 8, 0, tzinfo=timezone.utc)
    end = now + timedelta(hours=48)
    events = await client.list_events(start=now, end=end)

    assert len(events) == 1
    evt = events[0]
    assert evt.id == "abc123"
    assert evt.title == "Standup"
    assert evt.all_day is False
    assert evt.location == "Zoom"
    assert evt.start == datetime(2026, 4, 18, 9, 0, tzinfo=timezone.utc)
    assert evt.end == datetime(2026, 4, 18, 9, 30, tzinfo=timezone.utc)
    assert evt.is_recurring is False


# ---------------------------------------------------------------------------
# list_events — all-day events (AC 1)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_events_allday(client, oauth_service: MagicMock) -> None:
    """list_events correctly maps date (all-day) fields; all_day=True."""
    raw_evt = _make_allday_event(event_id="allday1", title="Feiertag", date="2026-04-19")
    mock_svc = _make_mock_service(list_response={"items": [raw_evt]})
    oauth_service.build_service.return_value = mock_svc

    events = await client.list_events()
    assert len(events) == 1
    evt = events[0]
    assert evt.all_day is True
    assert evt.start == datetime(2026, 4, 19, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# create_event (AC 2)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_event_calls_insert(client, oauth_service: MagicMock) -> None:
    """create_event calls events().insert() with correct body and returns CalendarEvent."""
    start = datetime(2026, 4, 20, 14, 0, tzinfo=timezone.utc)
    end = datetime(2026, 4, 20, 15, 0, tzinfo=timezone.utc)
    created_raw = _make_timed_event(
        event_id="new123",
        title="Meeting with Bob",
        start_iso=start.isoformat(),
        end_iso=end.isoformat(),
    )
    mock_svc = _make_mock_service(insert_response=created_raw)
    oauth_service.build_service.return_value = mock_svc

    result = await client.create_event(title="Meeting with Bob", start=start, end=end)

    mock_svc.events.return_value.insert.assert_called_once()
    call_kwargs = mock_svc.events.return_value.insert.call_args
    body = call_kwargs.kwargs.get("body") or call_kwargs.args[0] if call_kwargs.args else call_kwargs.kwargs.get("body")
    assert body is not None
    assert body["summary"] == "Meeting with Bob"
    assert result.id == "new123"


# ---------------------------------------------------------------------------
# update_event (AC 3)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_event_patches_and_returns(client, oauth_service: MagicMock) -> None:
    """update_event fetches, patches, calls events().update(), returns CalendarEvent."""
    original = _make_timed_event(event_id="evt1", title="Old Title")
    updated_raw = dict(original)
    updated_raw["summary"] = "New Title"

    mock_svc = _make_mock_service(get_response=original, update_response=updated_raw)
    oauth_service.build_service.return_value = mock_svc

    result = await client.update_event(event_id="evt1", title="New Title")

    mock_svc.events.return_value.update.assert_called_once()
    assert result.title == "New Title"


# ---------------------------------------------------------------------------
# delete_event (AC 4)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_event_calls_delete(client, oauth_service: MagicMock) -> None:
    """delete_event calls events().delete() exactly once."""
    mock_svc = _make_mock_service()
    oauth_service.build_service.return_value = mock_svc

    await client.delete_event(event_id="evt1")

    mock_svc.events.return_value.delete.assert_called_once_with(
        calendarId="primary", eventId="evt1"
    )


@pytest.mark.asyncio
async def test_delete_event_404_raises_calendar_error(
    client, oauth_service: MagicMock
) -> None:
    """delete_event raises CalendarClientError with spoken message on 404."""
    from integrations.google.calendar_client import CalendarClientError

    # Simulate an HttpError with status 404.
    http_error = Exception("404 Not Found")
    mock_resp = MagicMock()
    mock_resp.status = 404
    http_error.resp = mock_resp  # type: ignore[attr-defined]

    mock_svc = MagicMock()
    mock_svc.events.return_value.delete.return_value.execute.side_effect = http_error
    oauth_service.build_service.return_value = mock_svc

    with pytest.raises(CalendarClientError) as exc_info:
        await client.delete_event(event_id="missing")

    assert "couldn't find" in exc_info.value.spoken_message.lower()


# ---------------------------------------------------------------------------
# get_event
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_event_returns_event(client, oauth_service: MagicMock) -> None:
    """get_event fetches a single event and returns a CalendarEvent."""
    raw = _make_timed_event(event_id="single1", title="Solo meeting")
    mock_svc = _make_mock_service(get_response=raw)
    oauth_service.build_service.return_value = mock_svc

    result = await client.get_event("single1")
    assert result.id == "single1"
    assert result.title == "Solo meeting"


# ---------------------------------------------------------------------------
# Singleton factory (AC 14)
# ---------------------------------------------------------------------------


def test_get_calendar_client_singleton() -> None:
    """get_calendar_client() returns the same instance on repeated calls."""
    import integrations.google.calendar_client as _mod

    # Reset the singleton between test runs.
    original = _mod._calendar_client
    _mod._calendar_client = None

    try:
        # Patch at the source module so the inline import inside get_calendar_client picks it up.
        with patch("integrations.google.oauth.get_google_oauth_service") as mock_oauth:
            mock_oauth.return_value = MagicMock()
            c1 = _mod.get_calendar_client()
            c2 = _mod.get_calendar_client()
            assert c1 is c2
    finally:
        _mod._calendar_client = original


def test_get_calendar_client_fresh_after_reset() -> None:
    """A new instance is created after module reset (singleton cleared)."""
    import integrations.google.calendar_client as _mod

    original = _mod._calendar_client
    _mod._calendar_client = None

    try:
        # Patch at the source module so the inline import inside get_calendar_client picks it up.
        with patch("integrations.google.oauth.get_google_oauth_service") as mock_oauth:
            mock_oauth.return_value = MagicMock()
            c1 = _mod.get_calendar_client()
            _mod._calendar_client = None
            c2 = _mod.get_calendar_client()
            assert c1 is not c2
    finally:
        _mod._calendar_client = original
