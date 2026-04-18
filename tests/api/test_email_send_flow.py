"""End-to-end integration tests for the EMAIL_COMPOSE → confirm/cancel flow.

These tests exercise the full production path:
1. ``_attempt_email_compose_draft`` → create_draft called, pending state set,
   email_draft_preview broadcast.
2. ``_handle_email_confirm`` ("ja") → send_draft called, email_send_done broadcast,
   state cleared.
3. ``_handle_email_confirm`` ("nein") → send_draft NOT called, delete_draft called,
   state cleared.

No real OAuth / Gmail API calls are made.
"""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ws() -> MagicMock:
    """Build a minimal WebSocket mock."""
    return MagicMock()


def _make_intent_result(to: str = "max@test.de", subject: str = "Meeting") -> Any:
    """Build a fake IntentResult for EMAIL_COMPOSE."""
    from brain.intent_parser import Intent, IntentResult

    return IntentResult(
        intent=Intent.EMAIL_COMPOSE,
        confidence=0.85,
        params={"to": to, "subject": subject},
        original_text=f"E-Mail an {to} Betreff {subject}",
        language="de",
    )


async def _register_ws(ws: MagicMock) -> None:
    """Register a fake WebSocket in ws_server's connection state."""
    import api.ws_server as srv

    conn_id = id(ws)
    srv._connection_state[conn_id] = {
        "mode": "idle",
        "audio_chunks": [],
        "speech_started": False,
        "silent_samples": 0,
        "total_samples": 0,
        "skip_remaining": 0,
        "follow_up_timer_task": None,
        "pipeline_task": None,
        "current_run_id": None,
        "current_session_id": None,
        "barge_in_speech_started_at": None,
        "barge_in_pending": False,
        "barge_in_last_rms_log_at": 0.0,
        "barge_in_grace_until": 0.0,
        "last_backchannel_at": 0.0,
        "pending_email_send": None,
    }


async def _cleanup_ws(ws: MagicMock) -> None:
    import api.ws_server as srv

    srv._connection_state.pop(id(ws), None)


def _make_draft(draft_id: str = "draft_001", to: str = "max@test.de") -> Any:
    """Build a fake EmailDraft."""
    from datetime import datetime, timezone

    from integrations.google.gmail_client import EmailDraft

    return EmailDraft(
        id=draft_id,
        to=to,
        subject="Meeting",
        body="Hallo, wann treffen wir uns?",
        created_at=datetime(2024, 6, 1, tzinfo=timezone.utc),
    )


# ---------------------------------------------------------------------------
# Part 1 — _attempt_email_compose_draft populates pending state
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compose_draft_creates_draft_and_sets_pending_state():
    """_attempt_email_compose_draft calls create_draft and sets pending_email_send."""
    import api.ws_server as srv

    ws = _make_ws()
    await _register_ws(ws)

    intent = _make_intent_result(to="max@test.de", subject="Meeting")
    draft = _make_draft("draft_xyz", to="max@test.de")

    mock_client = MagicMock()
    mock_client.create_draft = AsyncMock(return_value=draft)

    draft_preview_broadcasts: list[dict] = []

    async def _capture_preview(payload: dict) -> None:
        draft_preview_broadcasts.append(payload)

    with (
        patch("api.ws_server.get_gmail_client", return_value=mock_client),
        patch(
            "api.ws_server.broadcast_email_draft_preview",
            side_effect=_capture_preview,
        ),
        patch("utils.config_loader.get_config") as mock_cfg,
    ):
        mock_cfg.return_value.get_section.return_value = {
            "enabled": True,
            "vip_senders": [],
        }
        await srv._attempt_email_compose_draft(ws, intent, "Entwurf erstellt")

    # Draft creation was called
    mock_client.create_draft.assert_awaited_once()
    call_kwargs = mock_client.create_draft.call_args
    assert call_kwargs.kwargs.get("to") == "max@test.de" or call_kwargs[1].get("to") == "max@test.de"

    # pending_email_send was set on the connection
    conn_state = srv._connection_state.get(id(ws))
    assert conn_state is not None
    pending = conn_state.get("pending_email_send")
    assert pending is not None
    assert pending["draft_id"] == "draft_xyz"
    assert pending["to"] == "max@test.de"
    assert "created_at" in pending

    # email_draft_preview was broadcast
    assert len(draft_preview_broadcasts) == 1
    preview_payload = draft_preview_broadcasts[0]
    assert preview_payload["draft_id"] == "draft_xyz"
    assert preview_payload["to"] == "max@test.de"

    await _cleanup_ws(ws)


@pytest.mark.asyncio
async def test_compose_draft_skips_when_no_recipient():
    """_attempt_email_compose_draft does not call create_draft when to is empty."""
    import api.ws_server as srv

    ws = _make_ws()
    await _register_ws(ws)

    intent = _make_intent_result(to="", subject="Meeting")

    mock_client = MagicMock()
    mock_client.create_draft = AsyncMock()

    with (
        patch("api.ws_server.get_gmail_client", return_value=mock_client),
        patch("utils.config_loader.get_config") as mock_cfg,
    ):
        mock_cfg.return_value.get_section.return_value = {
            "enabled": True,
            "vip_senders": [],
        }
        await srv._attempt_email_compose_draft(ws, intent, "")

    mock_client.create_draft.assert_not_awaited()

    conn_state = srv._connection_state.get(id(ws))
    assert conn_state is not None
    assert conn_state.get("pending_email_send") is None

    await _cleanup_ws(ws)


# ---------------------------------------------------------------------------
# Part 2 — confirm path ("ja"): send_draft called, state cleared
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_flow_confirm_sends_email():
    """Confirm phrase 'ja' after draft creation triggers send_draft (full path)."""
    import api.ws_server as srv

    ws = _make_ws()
    await _register_ws(ws)

    # Simulate that a draft was already created (pending state armed)
    conn_id = id(ws)
    srv._connection_state[conn_id]["pending_email_send"] = {
        "draft_id": "draft_001",
        "to": "max@test.de",
        "subject": "Meeting",
        "body_preview": "Hallo",
        "created_at": time.time(),
    }

    mock_client = MagicMock()
    mock_client.send_draft = AsyncMock(return_value="sent_msg_001")
    mock_client.delete_draft = AsyncMock(return_value=True)

    send_done_payloads: list[dict] = []

    async def _capture_done(payload: dict) -> None:
        send_done_payloads.append(payload)

    with (
        patch("api.ws_server.get_gmail_client", return_value=mock_client),
        patch("api.ws_server.broadcast_email_send_done", side_effect=_capture_done),
        patch("api.ws_server.broadcast_notification", new_callable=AsyncMock),
    ):
        consumed = await srv._handle_email_confirm(ws, "ja")

    assert consumed is True
    mock_client.send_draft.assert_awaited_once_with("draft_001")
    mock_client.delete_draft.assert_not_awaited()

    assert len(send_done_payloads) == 1
    assert send_done_payloads[0]["success"] is True
    assert send_done_payloads[0]["message_id"] == "sent_msg_001"

    # State cleared
    state = srv._connection_state.get(conn_id)
    assert state is not None
    assert state.get("pending_email_send") is None

    await _cleanup_ws(ws)


# ---------------------------------------------------------------------------
# Part 3 — cancel path ("nein"): send_draft NOT called, delete_draft called
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_flow_cancel_deletes_draft():
    """Cancel phrase 'nein' after draft creation calls delete_draft, not send_draft."""
    import api.ws_server as srv

    ws = _make_ws()
    await _register_ws(ws)

    conn_id = id(ws)
    srv._connection_state[conn_id]["pending_email_send"] = {
        "draft_id": "draft_002",
        "to": "max@test.de",
        "subject": "Meeting",
        "body_preview": "Hallo",
        "created_at": time.time(),
    }

    mock_client = MagicMock()
    mock_client.send_draft = AsyncMock(return_value="should_not_be_called")
    mock_client.delete_draft = AsyncMock(return_value=True)

    send_done_payloads: list[dict] = []

    async def _capture_done(payload: dict) -> None:
        send_done_payloads.append(payload)

    with (
        patch("api.ws_server.get_gmail_client", return_value=mock_client),
        patch("api.ws_server.broadcast_email_send_done", side_effect=_capture_done),
    ):
        consumed = await srv._handle_email_confirm(ws, "nein")

    assert consumed is True
    mock_client.send_draft.assert_not_awaited()
    mock_client.delete_draft.assert_awaited_once_with("draft_002")

    assert len(send_done_payloads) == 1
    assert send_done_payloads[0]["success"] is False

    state = srv._connection_state.get(conn_id)
    assert state is not None
    assert state.get("pending_email_send") is None

    await _cleanup_ws(ws)


# ---------------------------------------------------------------------------
# Verify call-site wiring: _handle_email_confirm is called in the pipeline
# ---------------------------------------------------------------------------


def test_handle_email_confirm_is_wired_in_pipeline():
    """Verify _handle_email_confirm is called inside _run_voice_pipeline_body."""
    import inspect

    import api.ws_server as srv

    source = inspect.getsource(srv._run_voice_pipeline_body)
    assert "_handle_email_confirm" in source, (
        "_handle_email_confirm must be called inside _run_voice_pipeline_body "
        "to intercept confirmation turns before the orchestrator."
    )


def test_attempt_email_compose_draft_is_wired_in_pipeline():
    """Verify _attempt_email_compose_draft is called inside _run_voice_pipeline_body."""
    import inspect

    import api.ws_server as srv

    source = inspect.getsource(srv._run_voice_pipeline_body)
    assert "_attempt_email_compose_draft" in source, (
        "_attempt_email_compose_draft must be called inside _run_voice_pipeline_body "
        "to create the draft after EMAIL_COMPOSE turns."
    )
