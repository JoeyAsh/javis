"""Unit tests for calendar broadcaster, poller, and proactive trigger.

Covers acceptance criteria 5, 6, 7, 8, 9.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_calendar_event(
    event_id: str = "evt1",
    title: str = "Standup",
    minutes_from_now: float = 10.0,
    all_day: bool = False,
) -> Any:
    """Build a mock CalendarEvent-like object."""
    from integrations.google.calendar_client import CalendarEvent

    now = datetime.now(timezone.utc)
    start = now + timedelta(minutes=minutes_from_now)
    end = start + timedelta(hours=1)
    return CalendarEvent(
        id=event_id,
        calendar_id="primary",
        title=title,
        start=start,
        end=end,
        all_day=all_day,
        location=None,
        description=None,
        attendees=[],
        is_recurring=False,
    )


# ---------------------------------------------------------------------------
# broadcast_calendar_state
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_broadcast_calendar_state_sends_correct_frame() -> None:
    """broadcast_calendar_state sends a correctly shaped WS frame to clients."""
    from api.ws_server import broadcast_calendar_state, _connected_clients

    mock_ws = MagicMock()
    mock_ws.send_str = AsyncMock()
    _connected_clients.add(mock_ws)

    try:
        events = [
            {
                "id": "evt1",
                "title": "Standup",
                "start": "2026-04-18T09:00:00+00:00",
                "end": "2026-04-18T09:30:00+00:00",
                "allDay": False,
                "location": None,
                "calendar": "primary",
            }
        ]
        await broadcast_calendar_state(events, "Heute")

        mock_ws.send_str.assert_called_once()
        import json

        frame = json.loads(mock_ws.send_str.call_args[0][0])
        assert frame["type"] == "calendar_state"
        assert frame["payload"]["dateLabel"] == "Heute"
        assert len(frame["payload"]["events"]) == 1
        assert frame["payload"]["events"][0]["title"] == "Standup"
    finally:
        _connected_clients.discard(mock_ws)


@pytest.mark.asyncio
async def test_broadcast_calendar_op_preview() -> None:
    """broadcast_calendar_op_preview sends the op preview frame."""
    from api.ws_server import broadcast_calendar_op_preview, _connected_clients
    import json

    mock_ws = MagicMock()
    mock_ws.send_str = AsyncMock()
    _connected_clients.add(mock_ws)

    try:
        await broadcast_calendar_op_preview(
            {
                "op": "create",
                "title": "Meeting",
                "start": "2026-04-19T14:00:00+00:00",
                "end": "2026-04-19T15:00:00+00:00",
                "confirm_prompt": "Create 'Meeting' tomorrow at 14:00?",
            }
        )
        frame = json.loads(mock_ws.send_str.call_args[0][0])
        assert frame["type"] == "calendar_op_preview"
        assert frame["payload"]["op"] == "create"
    finally:
        _connected_clients.discard(mock_ws)


@pytest.mark.asyncio
async def test_broadcast_calendar_op_done() -> None:
    """broadcast_calendar_op_done sends the op done frame."""
    from api.ws_server import broadcast_calendar_op_done, _connected_clients
    import json

    mock_ws = MagicMock()
    mock_ws.send_str = AsyncMock()
    _connected_clients.add(mock_ws)

    try:
        await broadcast_calendar_op_done({"op": "create", "success": True, "event_id": "new1"})
        frame = json.loads(mock_ws.send_str.call_args[0][0])
        assert frame["type"] == "calendar_op_done"
        assert frame["payload"]["success"] is True
    finally:
        _connected_clients.discard(mock_ws)


# ---------------------------------------------------------------------------
# _handle_calendar_confirm — confirm path (AC 7)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_calendar_confirm_confirm_word_consumes_turn() -> None:
    """Confirm word fires create_event, broadcasts op_done, clears state, returns True."""
    from api.ws_server import (
        _handle_calendar_confirm,
        _connection_state,
        broadcast_calendar_op_done,
    )

    ws = MagicMock()
    conn_id = id(ws)
    now_ts = time.time()

    start_dt = datetime.now(timezone.utc) + timedelta(hours=2)
    end_dt = start_dt + timedelta(hours=1)

    _connection_state[conn_id] = {
        "pending_calendar_op": {
            "op": "create",
            "title": "New Meeting",
            "start": start_dt.isoformat(),
            "end": end_dt.isoformat(),
            "event_id": None,
            "created_at": now_ts,
        }
    }

    mock_created_evt = MagicMock()
    mock_created_evt.id = "created_abc"
    mock_client = MagicMock()
    mock_client.create_event = AsyncMock(return_value=mock_created_evt)
    mock_client.list_events = AsyncMock(return_value=[])

    captured_frames: list[dict] = []

    async def mock_broadcast(payload: dict) -> None:
        captured_frames.append(payload)

    with (
        patch("api.ws_server.get_calendar_client", return_value=mock_client),
        patch("api.ws_server.broadcast_calendar_op_done", side_effect=mock_broadcast),
        patch("api.ws_server._force_calendar_state_refresh", new_callable=AsyncMock),
        patch("utils.config_loader.get_config", return_value=_mock_config()),
    ):
        result = await _handle_calendar_confirm(ws, "yes")

    assert result is True
    assert _connection_state[conn_id]["pending_calendar_op"] is None
    assert len(captured_frames) == 1
    assert captured_frames[0]["success"] is True
    assert captured_frames[0]["event_id"] == "created_abc"

    del _connection_state[conn_id]


# ---------------------------------------------------------------------------
# _handle_calendar_confirm — cancel path (AC 8)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_calendar_confirm_cancel_word_discards_op() -> None:
    """Cancel word discards op, broadcasts op_done{success:false}, returns True."""
    from api.ws_server import _handle_calendar_confirm, _connection_state

    ws = MagicMock()
    conn_id = id(ws)

    _connection_state[conn_id] = {
        "pending_calendar_op": {
            "op": "delete",
            "title": "Old Meeting",
            "start": "",
            "end": "",
            "event_id": "evt_old",
            "created_at": time.time(),
        }
    }

    captured_frames: list[dict] = []

    async def mock_broadcast(payload: dict) -> None:
        captured_frames.append(payload)

    with (
        patch("api.ws_server.broadcast_calendar_op_done", side_effect=mock_broadcast),
        patch("utils.config_loader.get_config", return_value=_mock_config()),
    ):
        result = await _handle_calendar_confirm(ws, "nein")

    assert result is True
    assert _connection_state[conn_id]["pending_calendar_op"] is None
    assert captured_frames[0]["success"] is False

    del _connection_state[conn_id]


# ---------------------------------------------------------------------------
# _handle_calendar_confirm — TTL expiry path (AC 9)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_calendar_confirm_ttl_expiry_returns_false() -> None:
    """Expired pending op returns False and clears state (turn processed normally)."""
    from api.ws_server import _handle_calendar_confirm, _connection_state

    ws = MagicMock()
    conn_id = id(ws)

    # Set created_at to 120 seconds ago (exceeds 60s timeout).
    _connection_state[conn_id] = {
        "pending_calendar_op": {
            "op": "create",
            "title": "Late Meeting",
            "start": "",
            "end": "",
            "event_id": None,
            "created_at": time.time() - 120,
        }
    }

    captured_done: list[dict] = []

    async def mock_broadcast(payload: dict) -> None:
        captured_done.append(payload)

    with (
        patch("api.ws_server.broadcast_calendar_op_done", side_effect=mock_broadcast),
        patch("api.ws_server.broadcast_notification", new_callable=AsyncMock),
        patch("utils.config_loader.get_config", return_value=_mock_config()),
    ):
        result = await _handle_calendar_confirm(ws, "Ich brauche Hilfe")

    assert result is False  # turn NOT consumed
    assert _connection_state[conn_id]["pending_calendar_op"] is None
    assert captured_done[0]["success"] is False

    del _connection_state[conn_id]


# ---------------------------------------------------------------------------
# _handle_calendar_confirm — no pending state
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_calendar_confirm_no_pending_returns_false() -> None:
    """Returns False immediately when no pending_calendar_op is set."""
    from api.ws_server import _handle_calendar_confirm, _connection_state

    ws = MagicMock()
    conn_id = id(ws)
    _connection_state[conn_id] = {"pending_calendar_op": None}

    result = await _handle_calendar_confirm(ws, "yes")
    assert result is False

    del _connection_state[conn_id]


# ---------------------------------------------------------------------------
# ProactiveScheduler cooldown bypass (AC 6)
# ---------------------------------------------------------------------------


def test_proactive_can_interject_calendar_bypasses_cooldown() -> None:
    """Calendar event type bypasses interjection cooldown."""
    from brain.proactive import ProactiveScheduler

    scheduler = ProactiveScheduler(
        event_bus=MagicMock(),
        config={"enabled": True, "interjection_cooldown_seconds": 300},
        tts_callback=AsyncMock(),
        ws_broadcaster=AsyncMock(),
    )
    # Simulate just-fired interjection (normally would block).
    scheduler._last_interjection_time = time.time()

    # Normal info event: blocked by cooldown.
    assert scheduler._can_interject("info", event_type="vip_mail") is False

    # Calendar event: bypasses cooldown.
    assert scheduler._can_interject("info", event_type="calendar_event_approaching") is True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_config() -> MagicMock:
    cfg = MagicMock()
    cfg.get_section.side_effect = lambda section: {
        "calendar": {
            "enabled": True,
            "op_confirm_timeout_seconds": 60,
            "lookahead_hours": 48,
            "max_events_per_query": 20,
        },
    }.get(section, {})
    return cfg
