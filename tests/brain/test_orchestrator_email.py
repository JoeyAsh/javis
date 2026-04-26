"""Tests for orchestrator email intent routing and confirmation state machine.

Covers intent matching via IntentParser and the confirmation gate in
ws_server._handle_email_confirm.

Uses pytest-asyncio; all external I/O is mocked.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Intent parser — email classification tests
# ---------------------------------------------------------------------------


@pytest.fixture()
def parser():
    """Return a live IntentParser instance."""
    from brain.intent_parser import IntentParser

    return IntentParser()


@pytest.mark.asyncio
async def test_email_read_english(parser):
    """'check my email' classifies as EMAIL_READ with conf >= 0.8."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("check my email", language="en")
    assert result.intent == Intent.EMAIL_READ
    assert result.confidence >= 0.8


@pytest.mark.asyncio
async def test_email_read_german(parser):
    """'Zeig meine E-Mails' classifies as EMAIL_READ with conf >= 0.8."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("Zeig meine E-Mails", language="de")
    assert result.intent == Intent.EMAIL_READ
    assert result.confidence >= 0.8


@pytest.mark.asyncio
async def test_email_read_unread_english(parser):
    """'Read my unread emails' classifies as EMAIL_READ."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("read my unread emails", language="en")
    assert result.intent == Intent.EMAIL_READ


@pytest.mark.asyncio
async def test_email_search_from_sender(parser):
    """'email from Sarah' classifies as EMAIL_SEARCH and extracts sender."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("email from Sarah", language="en")
    assert result.intent == Intent.EMAIL_SEARCH
    assert "sender" in result.params
    assert "sarah" in result.params["sender"].lower()


@pytest.mark.asyncio
async def test_email_search_german(parser):
    """'E-Mails von Sarah' classifies as EMAIL_SEARCH."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("E-Mails von Sarah suchen", language="de")
    assert result.intent == Intent.EMAIL_SEARCH


@pytest.mark.asyncio
async def test_email_compose_english(parser):
    """'send an email to John about the project' classifies as EMAIL_COMPOSE with to hint."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent(
        "send an email to John about the project", language="en"
    )
    assert result.intent == Intent.EMAIL_COMPOSE
    assert "to" in result.params
    assert result.params["to"]  # must be non-empty


@pytest.mark.asyncio
async def test_email_compose_german(parser):
    """'E-Mail an Klaus schreiben' classifies as EMAIL_COMPOSE."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("E-Mail an Klaus schreiben", language="de")
    assert result.intent == Intent.EMAIL_COMPOSE


@pytest.mark.asyncio
async def test_unrelated_text_is_not_email(parser):
    """'play some music' does not classify as any email intent."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("play some music", language="en")
    assert result.intent not in (
        Intent.EMAIL_READ,
        Intent.EMAIL_SEARCH,
        Intent.EMAIL_COMPOSE,
    )


# ---------------------------------------------------------------------------
# Confirmation state machine — ws_server._handle_email_confirm
# ---------------------------------------------------------------------------


def _make_ws() -> MagicMock:
    """Build a minimal WebSocket mock with a stable id()."""
    ws = MagicMock()
    return ws


async def _setup_server_state(
    ws: MagicMock,
    draft_id: str = "draft_001",
    to: str = "alice@x.com",
    created_at: float | None = None,
):
    """Inject a pending email state into _connection_state for the given ws mock."""
    import time

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
        "pending_email_send": {
            "draft_id": draft_id,
            "to": to,
            # Default to "just now" so timeout checks don't fire in tests
            "created_at": created_at if created_at is not None else time.time(),
        },
    }


async def _cleanup_server_state(ws: MagicMock):
    import api.ws_server as srv

    srv._connection_state.pop(id(ws), None)


@pytest.mark.asyncio
async def test_confirm_yes_calls_send_draft():
    """Confirm phrase 'ja' triggers send_draft and clears pending state."""
    import api.ws_server as srv

    ws = _make_ws()
    await _setup_server_state(ws, draft_id="draft_001")

    mock_client = MagicMock()
    mock_client.send_draft = AsyncMock(return_value="sent_msg_001")
    mock_client.delete_draft = AsyncMock(return_value=True)

    with (
        patch("api.ws_server.get_gmail_client", return_value=mock_client),
        patch("api.ws_server.broadcast_email_send_done", new_callable=AsyncMock),
        patch("api.ws_server.broadcast_notification", new_callable=AsyncMock),
    ):
        consumed = await srv._handle_email_confirm(ws, "ja senden")

    assert consumed is True
    mock_client.send_draft.assert_awaited_once_with("draft_001")

    state = srv._connection_state.get(id(ws))
    assert state is None or state.get("pending_email_send") is None
    await _cleanup_server_state(ws)


@pytest.mark.asyncio
async def test_confirm_yes_variants():
    """Various confirm phrases all trigger send_draft."""
    import api.ws_server as srv

    confirm_phrases = ["ja", "senden", "confirm", "yes", "send it", "go ahead", "bestätige"]
    for phrase in confirm_phrases:
        ws = _make_ws()
        safe_phrase = phrase.replace(" ", "_")
        await _setup_server_state(ws, draft_id=f"draft_{safe_phrase}")

        mock_client = MagicMock()
        mock_client.send_draft = AsyncMock(return_value="sent_ok")
        mock_client.delete_draft = AsyncMock(return_value=True)

        with (
            patch("api.ws_server.get_gmail_client", return_value=mock_client),
            patch("api.ws_server.broadcast_email_send_done", new_callable=AsyncMock),
            patch("api.ws_server.broadcast_notification", new_callable=AsyncMock),
        ):
            consumed = await srv._handle_email_confirm(ws, phrase)

        assert consumed is True, f"phrase {phrase!r} should be consumed"
        mock_client.send_draft.assert_awaited()
        await _cleanup_server_state(ws)


@pytest.mark.asyncio
async def test_confirm_no_calls_delete_draft():
    """Cancel phrase 'nein' calls delete_draft and does NOT call send_draft."""
    import api.ws_server as srv

    ws = _make_ws()
    await _setup_server_state(ws, draft_id="draft_002")

    mock_client = MagicMock()
    mock_client.send_draft = AsyncMock(return_value="should_not_be_called")
    mock_client.delete_draft = AsyncMock(return_value=True)

    with (
        patch("api.ws_server.get_gmail_client", return_value=mock_client),
        patch("api.ws_server.broadcast_email_send_done", new_callable=AsyncMock),
    ):
        consumed = await srv._handle_email_confirm(ws, "nein")


    assert consumed is True
    mock_client.send_draft.assert_not_awaited()
    mock_client.delete_draft.assert_awaited_once_with("draft_002")
    await _cleanup_server_state(ws)


@pytest.mark.asyncio
async def test_confirm_cancel_variants():
    """Various cancel phrases all abort without sending."""
    import api.ws_server as srv

    cancel_phrases = ["nein", "abbrechen", "stop", "cancel", "abort"]
    for phrase in cancel_phrases:
        ws = _make_ws()
        await _setup_server_state(ws, draft_id=f"draft_cancel_{phrase}")

        mock_client = MagicMock()
        mock_client.send_draft = AsyncMock()
        mock_client.delete_draft = AsyncMock(return_value=True)

        with (
            patch("api.ws_server.get_gmail_client", return_value=mock_client),
            patch("api.ws_server.broadcast_email_send_done", new_callable=AsyncMock),
        ):
            consumed = await srv._handle_email_confirm(ws, phrase)

        assert consumed is True, f"phrase {phrase!r} should be consumed"
        mock_client.send_draft.assert_not_awaited()
        await _cleanup_server_state(ws)


@pytest.mark.asyncio
async def test_ambiguous_phrase_not_consumed():
    """An ambiguous phrase does NOT consume the turn and keeps pending state."""
    import api.ws_server as srv

    ws = _make_ws()
    await _setup_server_state(ws, draft_id="draft_003")

    consumed = await srv._handle_email_confirm(ws, "what did you say?")
    assert consumed is False

    state = srv._connection_state.get(id(ws))
    assert state is not None and state.get("pending_email_send") is not None
    await _cleanup_server_state(ws)


@pytest.mark.asyncio
async def test_no_pending_state_returns_false():
    """_handle_email_confirm returns False immediately when no pending state exists."""
    import api.ws_server as srv

    ws = _make_ws()
    # Don't set up pending state — only a bare connection entry
    conn_id = id(ws)
    srv._connection_state[conn_id] = {"pending_email_send": None}

    consumed = await srv._handle_email_confirm(ws, "ja")
    assert consumed is False
    srv._connection_state.pop(conn_id, None)


@pytest.mark.asyncio
async def test_send_failure_broadcasts_failure_event():
    """When send_draft raises, broadcast_email_send_done is called with success=False."""
    import api.ws_server as srv

    ws = _make_ws()
    await _setup_server_state(ws, draft_id="draft_fail")

    mock_client = MagicMock()
    mock_client.send_draft = AsyncMock(side_effect=Exception("network down"))
    mock_client.delete_draft = AsyncMock(return_value=True)

    send_done_calls: list[dict] = []

    async def _capture_send_done(payload: dict) -> None:
        send_done_calls.append(payload)

    with (
        patch("api.ws_server.get_gmail_client", return_value=mock_client),
        patch("api.ws_server.broadcast_email_send_done", new_callable=AsyncMock,
              side_effect=_capture_send_done),
        patch("api.ws_server.broadcast_notification", new_callable=AsyncMock),
    ):
        consumed = await srv._handle_email_confirm(ws, "ja")

    assert consumed is True
    assert len(send_done_calls) == 1
    assert send_done_calls[0]["success"] is False
    assert "error" in send_done_calls[0]
    await _cleanup_server_state(ws)


# ---------------------------------------------------------------------------
# Orchestrator _build_email_context helper
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_email_context_gmail_disabled():
    """_build_email_context returns None when gmail.enabled is False."""
    from brain.intent_parser import Intent, IntentResult
    from brain.orchestrator import Orchestrator

    mock_claude = MagicMock()
    orch = Orchestrator(claude_client=mock_claude)

    intent_result = IntentResult(
        intent=Intent.EMAIL_READ,
        confidence=0.9,
        params={},
        original_text="check my email",
        language="en",
    )

    with patch("brain.orchestrator.get_config") as mock_cfg:
        mock_cfg.return_value.get_section.return_value = {"enabled": False}
        ctx = await orch._build_email_context(intent_result)

    assert ctx is None


@pytest.mark.asyncio
async def test_build_email_context_injects_unread_list():
    """_build_email_context returns a context string for EMAIL_READ."""
    from dataclasses import dataclass
    from datetime import datetime, timezone

    from brain.intent_parser import Intent, IntentResult
    from brain.orchestrator import Orchestrator
    from integrations.google.gmail_client import EmailMessage

    mock_claude = MagicMock()
    orch = Orchestrator(claude_client=mock_claude)

    fake_msg = EmailMessage(
        id="m1",
        thread_id="t1",
        subject="Hello",
        sender="Bob",
        sender_email="bob@example.com",
        recipient="me@example.com",
        received_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        snippet="Short preview",
        body_text=None,
        is_unread=True,
        is_vip=False,
    )

    mock_client = MagicMock()
    mock_client.list_unread = AsyncMock(return_value=[fake_msg])

    intent_result = IntentResult(
        intent=Intent.EMAIL_READ,
        confidence=0.9,
        params={},
        original_text="check my email",
        language="en",
    )

    with (
        patch("brain.orchestrator.get_config") as mock_cfg,
        patch(
            "integrations.google.gmail_client.get_gmail_client",
            return_value=mock_client,
        ),
    ):
        mock_cfg.return_value.get_section.return_value = {
            "enabled": True,
            "max_unread_summary": 5,
            "vip_senders": [],
        }
        ctx = await orch._build_email_context(intent_result)

    assert ctx is not None
    assert "Hello" in ctx
    assert "bob@example.com" in ctx


# ---------------------------------------------------------------------------
# Edge-case: "senden" with no pending draft is a normal turn
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_senden_without_pending_draft_is_normal_turn():
    """'senden' with no pending_email_send must return False (normal turn)."""
    import api.ws_server as srv

    ws = _make_ws()
    conn_id = id(ws)
    # Connection state exists but pending_email_send is None
    srv._connection_state[conn_id] = {
        "pending_email_send": None,
    }

    consumed = await srv._handle_email_confirm(ws, "senden")
    assert consumed is False, "'senden' with no pending draft must not be consumed"
    srv._connection_state.pop(conn_id, None)


# ---------------------------------------------------------------------------
# Edge-case: confirmation window timeout clears state
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_confirmation_window_expires_clears_state():
    """Expired confirmation window clears pending state; next turn is normal."""
    import time

    import api.ws_server as srv

    ws = _make_ws()
    conn_id = id(ws)
    srv._connection_state[conn_id] = {
        "pending_email_send": {
            "draft_id": "draft_expired",
            "to": "x@example.com",
            "subject": "Test",
            "body_preview": "Hello",
            # created_at far in the past — guaranteed to exceed any timeout
            "created_at": time.time() - 9999,
        },
    }

    mock_client = MagicMock()
    mock_client.delete_draft = AsyncMock(return_value=True)

    with (
        patch("api.ws_server.get_gmail_client", return_value=mock_client),
        patch("api.ws_server.broadcast_email_send_done", new_callable=AsyncMock),
        patch("api.ws_server.broadcast_notification", new_callable=AsyncMock),
        # Patch at the source module so the local import inside _handle_email_confirm
        # picks up the patched version.
        patch("utils.config_loader.get_config") as mock_cfg,
    ):
        mock_cfg.return_value.get_section.return_value = {
            "send_confirm_timeout_seconds": 60,
        }
        consumed = await srv._handle_email_confirm(ws, "ja")

    # Must NOT consume the turn — the window expired, so "ja" becomes a fresh intent
    assert consumed is False

    # State must be cleared
    state = srv._connection_state.get(conn_id)
    assert state is not None
    assert state.get("pending_email_send") is None

    srv._connection_state.pop(conn_id, None)
