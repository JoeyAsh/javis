"""Tests for mail_state broadcast shape and timing in ws_server.

Covers:
- broadcast_mail_state payload shape
- broadcast_email_draft_preview payload shape
- broadcast_email_send_done payload shape
- _start_mail_poller calls GmailClient.get_unread_count and
  broadcast_mail_state at the configured interval (AC 11)
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Broadcast helpers — payload shape tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_broadcast_mail_state_shape():
    """broadcast_mail_state emits a correctly shaped mail_state message."""
    sent: list[str] = []

    async def _fake_broadcast(msg: str) -> None:
        sent.append(msg)

    with patch("api.ws_server._broadcast", side_effect=_fake_broadcast):
        from api.ws_server import broadcast_mail_state

        messages = [
            {
                "id": "m1",
                "subject": "Hello",
                "sender": "Bob",
                "senderEmail": "bob@example.com",
                "isUnread": True,
                "isVip": False,
            }
        ]
        await broadcast_mail_state(messages, unread_count=3)

    assert len(sent) == 1
    payload = json.loads(sent[0])
    assert payload["type"] == "mail_state"
    assert payload["payload"]["unread_count"] == 3
    assert len(payload["payload"]["messages"]) == 1
    assert payload["payload"]["messages"][0]["id"] == "m1"


@pytest.mark.asyncio
async def test_broadcast_email_draft_preview_shape():
    """broadcast_email_draft_preview emits an email_draft_preview message."""
    sent: list[str] = []

    async def _fake_broadcast(msg: str) -> None:
        sent.append(msg)

    with patch("api.ws_server._broadcast", side_effect=_fake_broadcast):
        from api.ws_server import broadcast_email_draft_preview

        await broadcast_email_draft_preview(
            {
                "draft_id": "draft_001",
                "to": "alice@example.com",
                "subject": "Test",
                "body_preview": "Hello, Alice...",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    assert len(sent) == 1
    payload = json.loads(sent[0])
    assert payload["type"] == "email_draft_preview"
    assert payload["payload"]["draft_id"] == "draft_001"
    assert payload["payload"]["to"] == "alice@example.com"


@pytest.mark.asyncio
async def test_broadcast_email_send_done_success():
    """broadcast_email_send_done emits email_send_done with success=True."""
    sent: list[str] = []

    async def _fake_broadcast(msg: str) -> None:
        sent.append(msg)

    with patch("api.ws_server._broadcast", side_effect=_fake_broadcast):
        from api.ws_server import broadcast_email_send_done

        await broadcast_email_send_done(
            {"draft_id": "d1", "success": True, "message_id": "msg_001"}
        )

    payload = json.loads(sent[0])
    assert payload["type"] == "email_send_done"
    assert payload["payload"]["success"] is True
    assert payload["payload"]["message_id"] == "msg_001"


@pytest.mark.asyncio
async def test_broadcast_email_send_done_failure():
    """broadcast_email_send_done emits email_send_done with success=False."""
    sent: list[str] = []

    async def _fake_broadcast(msg: str) -> None:
        sent.append(msg)

    with patch("api.ws_server._broadcast", side_effect=_fake_broadcast):
        from api.ws_server import broadcast_email_send_done

        await broadcast_email_send_done(
            {"draft_id": "d2", "success": False, "error": "send failed"}
        )

    payload = json.loads(sent[0])
    assert payload["type"] == "email_send_done"
    assert payload["payload"]["success"] is False
    assert "error" in payload["payload"]


# ---------------------------------------------------------------------------
# Mail poller — interval and broadcast (AC 11)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mail_poller_calls_broadcast_mail_state():
    """_start_mail_poller calls broadcast_mail_state with correct data (AC 11)."""
    from datetime import datetime, timezone

    from integrations.google.gmail_client import EmailMessage

    fake_messages = [
        EmailMessage(
            id="m1",
            thread_id="t1",
            subject="Unread Test",
            sender="Alice",
            sender_email="alice@example.com",
            recipient="me@example.com",
            received_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            snippet="Snippet text",
            body_text=None,
            is_unread=True,
            is_vip=False,
        )
    ]

    mock_client = MagicMock()
    mock_client.list_unread = AsyncMock(return_value=fake_messages)
    mock_client.get_unread_count = AsyncMock(return_value=1)

    broadcast_calls: list[tuple[list[dict], int]] = []
    # After the first broadcast, raise CancelledError from asyncio.sleep so
    # the poller exits without needing to wait a real 120 s.
    sleep_calls = 0

    async def _fast_sleep(secs: float) -> None:
        nonlocal sleep_calls
        sleep_calls += 1
        if sleep_calls >= 2:
            raise asyncio.CancelledError()

    async def _capture_broadcast(messages: list[dict], unread_count: int) -> None:
        broadcast_calls.append((messages, unread_count))

    import api.ws_server as srv

    # Ensure the first-client event fires immediately so the poller doesn't block.
    srv._first_client_event.set()

    with (
        patch("api.ws_server.get_gmail_client", return_value=mock_client),
        patch("api.ws_server.broadcast_mail_state", side_effect=_capture_broadcast),
        patch("asyncio.sleep", side_effect=_fast_sleep),
    ):
        poller_task = asyncio.create_task(
            srv._start_mail_poller(poll_interval=1, vip_senders=[])
        )
        try:
            await poller_task
        except asyncio.CancelledError:
            pass

    # At least one broadcast should have fired
    assert len(broadcast_calls) >= 1
    messages_sent, count_sent = broadcast_calls[0]
    assert count_sent == 1
    assert len(messages_sent) == 1
    assert messages_sent[0]["id"] == "m1"


@pytest.mark.asyncio
async def test_mail_poller_survives_oauth_error():
    """_start_mail_poller does not crash on GoogleOAuthError — logs and continues."""
    from integrations.google.oauth import GoogleOAuthTokenError

    call_count = 0
    sleep_count = 0

    async def _mock_list_unread(max_results: int = 5):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise GoogleOAuthTokenError("expired")
        return []

    async def _mock_get_unread_count():
        return 0

    mock_client = MagicMock()
    mock_client.list_unread = AsyncMock(side_effect=_mock_list_unread)
    mock_client.get_unread_count = AsyncMock(side_effect=_mock_get_unread_count)

    import api.ws_server as srv

    srv._first_client_event.set()

    async def _controlled_sleep(secs: float) -> None:
        nonlocal sleep_count
        sleep_count += 1
        if sleep_count > 3:
            raise asyncio.CancelledError()

    with (
        patch("api.ws_server.get_gmail_client", return_value=mock_client),
        patch("api.ws_server.broadcast_mail_state", new_callable=AsyncMock),
        patch("asyncio.sleep", side_effect=_controlled_sleep),
    ):
        poller_task = asyncio.create_task(
            srv._start_mail_poller(poll_interval=1, vip_senders=[])
        )
        try:
            await poller_task
        except asyncio.CancelledError:
            pass

    # The poller ran at least one cycle without crashing
    assert call_count >= 1


@pytest.mark.asyncio
async def test_mail_poller_backoff_after_failures():
    """_start_mail_poller uses backoff sleep interval after 3 consecutive failures."""
    from integrations.google.gmail_client import GmailClientError

    mock_client = MagicMock()
    mock_client.list_unread = AsyncMock(
        side_effect=GmailClientError("rate limit", "Gmail ist nicht erreichbar.")
    )
    mock_client.get_unread_count = AsyncMock(
        side_effect=GmailClientError("rate limit", "Gmail ist nicht erreichbar.")
    )

    sleep_intervals: list[float] = []
    sleep_call_count = 0

    async def _capture_sleep(secs: float) -> None:
        nonlocal sleep_call_count
        sleep_intervals.append(secs)
        sleep_call_count += 1
        if sleep_call_count > 5:
            raise asyncio.CancelledError()

    import api.ws_server as srv

    srv._first_client_event.set()

    with (
        patch("api.ws_server.get_gmail_client", return_value=mock_client),
        patch("api.ws_server.broadcast_mail_state", new_callable=AsyncMock),
        patch("asyncio.sleep", side_effect=_capture_sleep),
    ):
        poller_task = asyncio.create_task(
            srv._start_mail_poller(poll_interval=120, vip_senders=[])
        )
        try:
            await poller_task
        except asyncio.CancelledError:
            pass

    # After 3 consecutive failures, the interval switches to 3x normal (360 s).
    # With 6 sleep calls, at least one should be >= 360.
    assert len(sleep_intervals) > 0
    if len(sleep_intervals) > 3:
        assert any(s >= 360 for s in sleep_intervals)


# ---------------------------------------------------------------------------
# _email_message_to_dict helper shape
# ---------------------------------------------------------------------------


def test_email_message_to_dict_shape():
    """_email_message_to_dict produces camelCase keys matching the TS MailMessage type."""
    from datetime import datetime, timezone

    from api.ws_server import _email_message_to_dict
    from integrations.google.gmail_client import EmailMessage

    msg = EmailMessage(
        id="abc",
        thread_id="thr1",
        subject="Hello",
        sender="Bob",
        sender_email="bob@x.com",
        recipient="me@x.com",
        received_at=datetime(2024, 6, 1, tzinfo=timezone.utc),
        snippet="snip",
        body_text=None,
        is_unread=True,
        is_vip=True,
    )
    d = _email_message_to_dict(msg)
    assert d["id"] == "abc"
    assert d["threadId"] == "thr1"
    assert d["senderEmail"] == "bob@x.com"
    # Frontend TS type uses "preview" (not "snippet") and "unread" (not "isUnread")
    assert d["preview"] == "snip"
    assert d["unread"] is True
    assert d["isVip"] is True
    assert "receivedAt" in d
    # Verify legacy keys are NOT present (would break the TS type)
    assert "snippet" not in d
    assert "isUnread" not in d
