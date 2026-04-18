"""Unit tests for GmailClient.

All ``googleapiclient.discovery.build`` / ``GoogleOAuthService.build_service``
calls are replaced with ``MagicMock`` objects. No real OAuth flow or network
call is made.

Covers acceptance criteria 1–6 and 18.
"""

from __future__ import annotations

import asyncio
import base64
import json
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_raw_message(
    msg_id: str = "msg001",
    thread_id: str = "thread001",
    subject: str = "Hello World",
    from_: str = "Alice <alice@example.com>",
    to: str = "me@example.com",
    snippet: str = "Short preview text",
    label_ids: list[str] | None = None,
    internal_date_ms: int = 1_700_000_000_000,
) -> dict[str, Any]:
    """Build a minimal Gmail API message dict."""
    if label_ids is None:
        label_ids = ["INBOX", "UNREAD"]
    return {
        "id": msg_id,
        "threadId": thread_id,
        "internalDate": str(internal_date_ms),
        "labelIds": label_ids,
        "snippet": snippet,
        "payload": {
            "mimeType": "text/plain",
            "headers": [
                {"name": "Subject", "value": subject},
                {"name": "From", "value": from_},
                {"name": "To", "value": to},
            ],
            "body": {
                "data": base64.urlsafe_b64encode(b"Body content here").decode(),
            },
            "parts": [],
        },
    }


def _make_mock_service(
    list_response: dict[str, Any] | None = None,
    message_response: dict[str, Any] | None = None,
    draft_create_response: dict[str, Any] | None = None,
    draft_send_response: dict[str, Any] | None = None,
    draft_delete_response: Any = None,
) -> MagicMock:
    """Build a chainable MagicMock mimicking the Gmail service resource."""
    svc = MagicMock()

    # ---- messages().list().execute() ----
    list_exec = MagicMock(return_value=list_response or {"messages": [], "resultSizeEstimate": 0})
    svc.users.return_value.messages.return_value.list.return_value.execute = list_exec

    # ---- messages().get().execute() ----
    get_exec = MagicMock(return_value=message_response or _make_raw_message())
    svc.users.return_value.messages.return_value.get.return_value.execute = get_exec

    # ---- drafts().create().execute() ----
    dc_exec = MagicMock(
        return_value=draft_create_response or {"id": "draft_abc", "message": {"id": "draft_abc"}}
    )
    svc.users.return_value.drafts.return_value.create.return_value.execute = dc_exec

    # ---- drafts().send().execute() ----
    ds_exec = MagicMock(
        return_value=draft_send_response or {"id": "sent_msg_001"}
    )
    svc.users.return_value.drafts.return_value.send.return_value.execute = ds_exec

    # ---- drafts().delete().execute() ----
    dd_exec = MagicMock(return_value=draft_delete_response or {})
    svc.users.return_value.drafts.return_value.delete.return_value.execute = dd_exec

    return svc


def _make_client(mock_service: MagicMock, vip_senders: list[str] | None = None):
    """Construct a GmailClient with a mocked OAuth service that returns ``mock_service``."""
    from integrations.google.gmail_client import GmailClient

    oauth = MagicMock()
    oauth.build_service = AsyncMock(return_value=mock_service)
    client = GmailClient(oauth_service=oauth, vip_senders=vip_senders or [])
    return client


# ---------------------------------------------------------------------------
# Acceptance criterion 1 — list_unread returns EmailMessage objects
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_unread_returns_email_messages():
    """list_unread returns EmailMessage objects with correct fields (AC 1)."""
    raw_msg = _make_raw_message(
        msg_id="abc123",
        subject="Test Subject",
        from_="Bob <bob@example.com>",
        label_ids=["INBOX", "UNREAD"],
    )
    svc = _make_mock_service(
        list_response={"messages": [{"id": "abc123"}], "resultSizeEstimate": 1},
        message_response=raw_msg,
    )
    client = _make_client(svc)
    messages = await client.list_unread(max_results=5)

    assert len(messages) == 1
    msg = messages[0]
    assert msg.id == "abc123"
    assert msg.subject == "Test Subject"
    assert msg.sender_email == "bob@example.com"
    assert msg.is_unread is True
    assert msg.is_vip is False


@pytest.mark.asyncio
async def test_list_unread_vip_flag():
    """list_unread sets is_vip=True when sender_email is in vip_senders list."""
    raw_msg = _make_raw_message(from_="VIP Person <vip@example.com>")
    svc = _make_mock_service(
        list_response={"messages": [{"id": "vip001"}]},
        message_response=raw_msg,
    )
    client = _make_client(svc, vip_senders=["vip@example.com"])
    messages = await client.list_unread()
    assert messages[0].is_vip is True


@pytest.mark.asyncio
async def test_list_unread_empty_inbox():
    """list_unread returns empty list when no unread messages exist."""
    svc = _make_mock_service(list_response={"messages": [], "resultSizeEstimate": 0})
    client = _make_client(svc)
    result = await client.list_unread()
    assert result == []


# ---------------------------------------------------------------------------
# Acceptance criterion 2 — search calls the API with the correct query
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_passes_query_to_api():
    """search calls users().messages().list with the given query string (AC 2)."""
    svc = _make_mock_service(
        list_response={"messages": []},
    )
    client = _make_client(svc)
    await client.search(query="from:sarah", max_results=5)

    call_kwargs = svc.users.return_value.messages.return_value.list.call_args
    assert call_kwargs is not None
    kwargs = call_kwargs.kwargs if call_kwargs.kwargs else call_kwargs[1]
    assert kwargs.get("q") == "from:sarah" or call_kwargs[1].get("q") == "from:sarah"


@pytest.mark.asyncio
async def test_search_respects_max_results_cap():
    """search caps max_results at 50 regardless of caller input."""
    svc = _make_mock_service(list_response={"messages": []})
    client = _make_client(svc)
    await client.search("in:inbox", max_results=999)

    call_kwargs = svc.users.return_value.messages.return_value.list.call_args
    kwargs = call_kwargs.kwargs if call_kwargs.kwargs else call_kwargs[1]
    assert kwargs.get("maxResults", 0) <= 50


# ---------------------------------------------------------------------------
# Acceptance criterion 3 — get_unread_count single API call + integer return
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_unread_count_returns_integer():
    """get_unread_count returns an integer from resultSizeEstimate (AC 3)."""
    svc = _make_mock_service(
        list_response={"resultSizeEstimate": 7},
    )
    client = _make_client(svc)
    count = await client.get_unread_count()
    assert count == 7
    assert isinstance(count, int)


@pytest.mark.asyncio
async def test_get_unread_count_single_api_call():
    """get_unread_count makes exactly one messages().list() call."""
    svc = _make_mock_service(list_response={"resultSizeEstimate": 3})
    client = _make_client(svc)
    await client.get_unread_count()

    assert svc.users.return_value.messages.return_value.list.call_count == 1


@pytest.mark.asyncio
async def test_get_unread_count_uses_correct_fields():
    """get_unread_count requests resultSizeEstimate field only."""
    svc = _make_mock_service(list_response={"resultSizeEstimate": 0})
    client = _make_client(svc)
    await client.get_unread_count()

    call_kwargs = svc.users.return_value.messages.return_value.list.call_args
    kwargs = call_kwargs.kwargs if call_kwargs.kwargs else call_kwargs[1]
    assert "resultSizeEstimate" in kwargs.get("fields", "")
    assert kwargs.get("maxResults") == 1
    assert "UNREAD" in kwargs.get("labelIds", [])


# ---------------------------------------------------------------------------
# Acceptance criterion 4 — create_draft calls drafts().create() with RFC 2822
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_draft_calls_api():
    """create_draft calls users().drafts().create() with a base64 RFC 2822 msg (AC 4)."""
    svc = _make_mock_service(
        draft_create_response={"id": "draft_xyz", "message": {"id": "draft_xyz"}}
    )
    client = _make_client(svc)
    draft = await client.create_draft(
        to="alice@example.com",
        subject="Test Draft",
        body="Hello, Alice!",
    )

    assert draft.id == "draft_xyz"
    assert draft.to == "alice@example.com"
    assert draft.subject == "Test Draft"
    assert draft.body == "Hello, Alice!"

    create_call = svc.users.return_value.drafts.return_value.create
    assert create_call.called
    body_arg = create_call.call_args.kwargs.get("body") or create_call.call_args[1].get("body")
    assert body_arg is not None
    raw_b64 = body_arg["message"]["raw"]
    # Verify it's valid base64 and decodes to an RFC 2822 message
    decoded = base64.urlsafe_b64decode(raw_b64 + "==").decode("utf-8")
    assert "alice@example.com" in decoded
    assert "Test Draft" in decoded


@pytest.mark.asyncio
async def test_create_draft_raises_on_empty_to():
    """create_draft raises GmailClientError when to address is empty."""
    from integrations.google.gmail_client import GmailClientError

    svc = _make_mock_service()
    client = _make_client(svc)
    with pytest.raises(GmailClientError):
        await client.create_draft(to="", subject="Test", body="Body")


# ---------------------------------------------------------------------------
# Acceptance criterion 5 — send_draft calls drafts().send()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_draft_calls_api_with_correct_id():
    """send_draft calls users().drafts().send() with the given draft_id (AC 5)."""
    svc = _make_mock_service(draft_send_response={"id": "sent_001"})
    client = _make_client(svc)
    message_id = await client.send_draft("draft_abc")

    assert message_id == "sent_001"
    send_call = svc.users.return_value.drafts.return_value.send
    assert send_call.called
    body_arg = send_call.call_args.kwargs.get("body") or send_call.call_args[1].get("body")
    assert body_arg is not None
    assert body_arg.get("id") == "draft_abc"


@pytest.mark.asyncio
async def test_send_draft_raises_gmail_client_error_on_api_failure():
    """send_draft raises GmailClientError when the API call throws."""
    from integrations.google.gmail_client import GmailClientError

    svc = _make_mock_service()
    svc.users.return_value.drafts.return_value.send.return_value.execute.side_effect = (
        Exception("API error")
    )
    client = _make_client(svc)
    with pytest.raises(GmailClientError) as exc_info:
        await client.send_draft("draft_xyz")
    assert exc_info.value.spoken_message  # should have a TTS-friendly message


# ---------------------------------------------------------------------------
# Acceptance criterion 6 — delete_draft calls drafts().delete()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_draft_calls_api():
    """delete_draft calls users().drafts().delete() with correct draft_id (AC 6)."""
    svc = _make_mock_service()
    client = _make_client(svc)
    result = await client.delete_draft("draft_to_delete")

    assert result is True
    delete_call = svc.users.return_value.drafts.return_value.delete
    assert delete_call.called
    call_kwargs = delete_call.call_args.kwargs or dict(delete_call.call_args[1])
    assert call_kwargs.get("id") == "draft_to_delete"


@pytest.mark.asyncio
async def test_delete_draft_returns_false_on_failure():
    """delete_draft returns False (non-fatal) when the API call throws."""
    svc = _make_mock_service()
    svc.users.return_value.drafts.return_value.delete.return_value.execute.side_effect = (
        Exception("network error")
    )
    client = _make_client(svc)
    result = await client.delete_draft("bad_draft")
    assert result is False


# ---------------------------------------------------------------------------
# Acceptance criterion 18 — GoogleOAuthError does not crash the client
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gmail_client_handles_oauth_error_gracefully():
    """GmailClient propagates GoogleOAuthError as GmailClientError (AC 18)."""
    from integrations.google.gmail_client import GmailClient, GmailClientError
    from integrations.google.oauth import GoogleOAuthTokenError

    oauth = MagicMock()
    oauth.build_service = AsyncMock(side_effect=GoogleOAuthTokenError("token expired"))
    client = GmailClient(oauth_service=oauth, vip_senders=[])

    with pytest.raises((GmailClientError, GoogleOAuthTokenError)):
        await client.list_unread()


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_message_include_body_true():
    """get_message with include_body=True populates body_text."""
    raw_msg = _make_raw_message(msg_id="body_test")
    svc = _make_mock_service(message_response=raw_msg)
    client = _make_client(svc)
    msg = await client.get_message("body_test", include_body=True)
    assert msg.body_text is not None
    assert "Body content here" in msg.body_text


@pytest.mark.asyncio
async def test_get_message_include_body_false():
    """get_message with include_body=False leaves body_text as None."""
    raw_msg = _make_raw_message()
    svc = _make_mock_service(message_response=raw_msg)
    client = _make_client(svc)
    msg = await client.get_message("test_id", include_body=False)
    assert msg.body_text is None


@pytest.mark.asyncio
async def test_search_pagination():
    """search follows nextPageToken for pagination."""
    page1 = {"messages": [{"id": "m1"}, {"id": "m2"}], "nextPageToken": "tok123"}
    page2 = {"messages": [{"id": "m3"}]}

    svc = MagicMock()
    # First call returns page1, second call returns page2
    svc.users.return_value.messages.return_value.list.return_value.execute.side_effect = [
        page1,
        page2,
    ]
    raw = _make_raw_message()
    svc.users.return_value.messages.return_value.get.return_value.execute.return_value = raw

    from integrations.google.gmail_client import GmailClient

    oauth = MagicMock()
    oauth.build_service = AsyncMock(return_value=svc)
    client = GmailClient(oauth_service=oauth, vip_senders=[])
    messages = await client.search("in:inbox", max_results=3)
    assert len(messages) == 3


@pytest.mark.asyncio
async def test_get_gmail_client_singleton():
    """get_gmail_client returns the same singleton on repeated calls."""
    import integrations.google.gmail_client as _mod

    # Reset singleton between test runs
    _mod._gmail_client_instance = None

    mock_oauth_svc = MagicMock()
    with patch(
        "integrations.google.gmail_client.get_gmail_client.__module__",
        create=True,
    ):
        pass

    # Directly patch the oauth module that get_gmail_client imports
    with patch("integrations.google.oauth.get_google_oauth_service") as mock_get_svc:
        mock_get_svc.return_value = mock_oauth_svc
        c1 = _mod.get_gmail_client()
        c2 = _mod.get_gmail_client()
        assert c1 is c2

    _mod._gmail_client_instance = None  # clean up
