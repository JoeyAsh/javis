"""Unit tests for GmailClient — gog CLI adapter (ADR-0001 migration).

All calls to ``run_gog`` are replaced with ``AsyncMock`` objects.
No real subprocess is ever spawned; no live Gmail API calls are made.

Covers acceptance criteria:
- AC 3: EmailMessage dataclass shape is unchanged
- AC 3: list_unread / search / get_message / get_unread_count happy paths
- AC 4: GogCommandError → GmailClientError propagation
- AC 4: GogNotInstalledError → GmailClientError propagation
- AC 3: create_draft / send_draft / delete_draft happy paths
- Edge: empty recipient raises GmailClientError immediately
- Edge: delete_draft returns False (non-fatal) on error
- Edge: get_unread_count with nextPageToken paginates
- Edge: VIP flag detection
- Edge: singleton factory
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def gmail_client():
    """Return a GmailClient with a fixed account and no VIP senders."""
    from integrations.google.gmail_client import GmailClient

    return GmailClient(account=None, vip_senders=[], timeout_seconds=5.0)


@pytest.fixture()
def vip_client():
    """Return a GmailClient with vip@example.com in the VIP list."""
    from integrations.google.gmail_client import GmailClient

    return GmailClient(account=None, vip_senders=["vip@example.com"], timeout_seconds=5.0)


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _gog_message(
    msg_id: str = "msg001",
    thread_id: str = "thread001",
    subject: str = "Hello World",
    from_: str = "Alice <alice@example.com>",
    to: str = "me@example.com",
    snippet: str = "Short preview text",
    labels: list[str] | None = None,
    date: str = "2026-04-25 17:29",
    body: str | None = None,
) -> dict[str, Any]:
    """Build a minimal gog JSON message dict."""
    raw: dict[str, Any] = {
        "id": msg_id,
        "threadId": thread_id,
        "date": date,
        "from": from_,
        "subject": subject,
        "snippet": snippet,
        "labels": labels if labels is not None else ["UNREAD", "INBOX"],
        "to": to,
    }
    if body is not None:
        raw["body"] = body
    return raw


def _search_response(*messages: dict[str, Any], next_page_token: str | None = None) -> dict[str, Any]:
    """Build a gog search response dict."""
    result: dict[str, Any] = {"messages": list(messages)}
    if next_page_token:
        result["nextPageToken"] = next_page_token
    return result


# ---------------------------------------------------------------------------
# Dataclass shape smoke tests (AC #2)
# ---------------------------------------------------------------------------


def test_email_message_dataclass_shape():
    """EmailMessage dataclass fields are unchanged from before migration."""
    from integrations.google.gmail_client import EmailMessage

    msg = EmailMessage(
        id="abc",
        thread_id="thr1",
        subject="Test",
        sender="Bob",
        sender_email="bob@example.com",
        recipient="me@example.com",
        received_at=datetime(2026, 4, 25, 17, 29, tzinfo=timezone.utc),
        snippet="Preview text",
        body_text="Full body",
        is_unread=True,
        is_vip=False,
    )
    assert msg.id == "abc"
    assert msg.thread_id == "thr1"
    assert msg.is_unread is True
    assert msg.is_vip is False


def test_email_draft_dataclass_shape():
    """EmailDraft dataclass has expected fields."""
    from integrations.google.gmail_client import EmailDraft

    draft = EmailDraft(id="d1", to="alice@example.com", subject="Hi", body="Hello")
    assert draft.id == "d1"
    assert draft.to == "alice@example.com"
    assert isinstance(draft.created_at, datetime)


# ---------------------------------------------------------------------------
# _parse_gog_message helper
# ---------------------------------------------------------------------------


def test_parse_gog_message_timed_event():
    """_parse_gog_message correctly parses a standard gog message dict."""
    from integrations.google.gmail_client import _parse_gog_message

    raw = _gog_message(
        msg_id="id1",
        subject="=?utf-8?b?SGVsbG8=?=",  # RFC-2047 encoded "Hello"
        from_="Bob Jones <bob@example.com>",
        labels=["UNREAD", "INBOX"],
        date="2026-04-20 09:00",
    )
    msg = _parse_gog_message(raw, vip_senders=["bob@example.com"])
    assert msg.id == "id1"
    assert msg.subject == "Hello"
    assert msg.sender == "Bob Jones"
    assert msg.sender_email == "bob@example.com"
    assert msg.is_unread is True
    assert msg.is_vip is True
    assert msg.received_at.tzinfo is not None


def test_parse_gog_message_missing_date_falls_back():
    """_parse_gog_message uses datetime.now fallback when date is absent."""
    from integrations.google.gmail_client import _parse_gog_message

    raw = _gog_message(date="")
    before = datetime.now(timezone.utc)
    msg = _parse_gog_message(raw, vip_senders=[])
    after = datetime.now(timezone.utc)
    assert before <= msg.received_at <= after


def test_parse_gog_message_invalid_date_falls_back():
    """_parse_gog_message handles an unparseable date string gracefully."""
    from integrations.google.gmail_client import _parse_gog_message

    raw = _gog_message(date="not-a-date")
    msg = _parse_gog_message(raw, vip_senders=[])
    assert isinstance(msg.received_at, datetime)


def test_parse_gog_message_body_from_body_field():
    """_parse_gog_message reads body_text from the 'body' key."""
    from integrations.google.gmail_client import _parse_gog_message

    raw = _gog_message(body="Full message text here")
    msg = _parse_gog_message(raw, vip_senders=[])
    assert msg.body_text == "Full message text here"


# ---------------------------------------------------------------------------
# GmailClient.list_unread happy path (AC #3)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_unread_returns_email_messages(gmail_client):
    """list_unread returns correctly parsed EmailMessage objects."""
    from integrations.google.gmail_client import EmailMessage

    canned = _search_response(_gog_message(msg_id="abc", subject="Test Subject"))
    with patch(
        "integrations.google.gmail_client.run_gog",
        new=AsyncMock(return_value=canned),
    ):
        messages = await gmail_client.list_unread(max_results=5)

    assert len(messages) == 1
    assert isinstance(messages[0], EmailMessage)
    assert messages[0].id == "abc"
    assert messages[0].subject == "Test Subject"
    assert messages[0].is_unread is True


@pytest.mark.asyncio
async def test_list_unread_vip_flag(vip_client):
    """list_unread sets is_vip=True when sender_email matches vip_senders."""
    canned = _search_response(_gog_message(from_="VIP Person <vip@example.com>"))
    with patch(
        "integrations.google.gmail_client.run_gog",
        new=AsyncMock(return_value=canned),
    ):
        messages = await vip_client.list_unread()

    assert messages[0].is_vip is True


@pytest.mark.asyncio
async def test_list_unread_empty_inbox(gmail_client):
    """list_unread returns empty list when gog returns no messages."""
    with patch(
        "integrations.google.gmail_client.run_gog",
        new=AsyncMock(return_value={"messages": []}),
    ):
        result = await gmail_client.list_unread()

    assert result == []


@pytest.mark.asyncio
async def test_list_unread_caps_at_50(gmail_client):
    """list_unread caps max_results at 50."""
    captured: list[tuple] = []

    async def capture_run(*args: str, **kwargs: Any) -> dict:
        captured.append(args)
        return {"messages": []}

    with patch("integrations.google.gmail_client.run_gog", side_effect=capture_run):
        await gmail_client.list_unread(max_results=999)

    # "--max" arg should be "50"
    assert "--max" in captured[0]
    idx = captured[0].index("--max")
    assert captured[0][idx + 1] == "50"


@pytest.mark.asyncio
async def test_list_unread_sender_filter_appended(gmail_client):
    """list_unread appends from:<sender> to the query when sender is given."""
    captured: list[tuple] = []

    async def capture_run(*args: str, **kwargs: Any) -> dict:
        captured.append(args)
        return {"messages": []}

    with patch("integrations.google.gmail_client.run_gog", side_effect=capture_run):
        await gmail_client.list_unread(sender="alice@example.com")

    query_arg = captured[0][3]  # "gmail", "messages", "search", <QUERY>
    assert "from:alice@example.com" in query_arg


# ---------------------------------------------------------------------------
# GmailClient.search (AC #3)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_passes_query_and_returns_messages(gmail_client):
    """search calls run_gog with the expected args and parses results."""
    canned = _search_response(
        _gog_message(msg_id="s1"),
        _gog_message(msg_id="s2"),
    )
    captured: list[tuple] = []

    async def capture_run(*args: str, **kwargs: Any) -> dict:
        captured.append(args)
        return canned

    with patch("integrations.google.gmail_client.run_gog", side_effect=capture_run):
        results = await gmail_client.search("from:boss is:unread", max_results=10)

    assert len(results) == 2
    assert "gmail" in captured[0]
    assert "from:boss is:unread" in captured[0]


@pytest.mark.asyncio
async def test_search_caps_max_results(gmail_client):
    """search caps max_results at 50."""
    captured: list[tuple] = []

    async def capture_run(*args: str, **kwargs: Any) -> dict:
        captured.append(args)
        return {"messages": []}

    with patch("integrations.google.gmail_client.run_gog", side_effect=capture_run):
        await gmail_client.search("in:inbox", max_results=200)

    idx = captured[0].index("--max")
    assert captured[0][idx + 1] == "50"


# ---------------------------------------------------------------------------
# GmailClient.get_message (AC #3)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_message_include_body_true(gmail_client):
    """get_message returns a message with body_text when include_body=True."""
    canned = _search_response(_gog_message(msg_id="bodymsg", body="Full body text"))
    with patch(
        "integrations.google.gmail_client.run_gog",
        new=AsyncMock(return_value=canned),
    ):
        msg = await gmail_client.get_message("bodymsg", include_body=True)

    assert msg.body_text == "Full body text"


@pytest.mark.asyncio
async def test_get_message_include_body_false(gmail_client):
    """get_message leaves body_text as None when include_body=False."""
    canned = _search_response(_gog_message(msg_id="nob", body="Some body"))
    with patch(
        "integrations.google.gmail_client.run_gog",
        new=AsyncMock(return_value=canned),
    ):
        msg = await gmail_client.get_message("nob", include_body=False)

    assert msg.body_text is None


@pytest.mark.asyncio
async def test_get_message_not_found_raises(gmail_client):
    """get_message raises GmailClientError when gog returns no messages."""
    from integrations.google.gmail_client import GmailClientError

    with patch(
        "integrations.google.gmail_client.run_gog",
        new=AsyncMock(return_value={"messages": []}),
    ):
        with pytest.raises(GmailClientError) as exc_info:
            await gmail_client.get_message("missing_id")

    assert exc_info.value.spoken_message


# ---------------------------------------------------------------------------
# GmailClient.get_unread_count (AC #3)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_unread_count_returns_integer(gmail_client):
    """get_unread_count returns the number of messages in the response."""
    canned = _search_response(
        _gog_message("m1"), _gog_message("m2"), _gog_message("m3")
    )
    with patch(
        "integrations.google.gmail_client.run_gog",
        new=AsyncMock(return_value=canned),
    ):
        count = await gmail_client.get_unread_count()

    assert count == 3
    assert isinstance(count, int)


@pytest.mark.asyncio
async def test_get_unread_count_with_next_page_token(gmail_client):
    """get_unread_count returns at least 100 when nextPageToken is present."""
    canned = _search_response(
        *[_gog_message(str(i)) for i in range(5)],
        next_page_token="tok123",
    )
    with patch(
        "integrations.google.gmail_client.run_gog",
        new=AsyncMock(return_value=canned),
    ):
        count = await gmail_client.get_unread_count()

    assert count >= 100


# ---------------------------------------------------------------------------
# GmailClient.create_draft (AC #3)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_draft_returns_email_draft(gmail_client):
    """create_draft calls gog and returns an EmailDraft with the correct id."""
    from integrations.google.gmail_client import EmailDraft

    canned = {"id": "draft_xyz"}
    with patch(
        "integrations.google.gmail_client.run_gog",
        new=AsyncMock(return_value=canned),
    ):
        draft = await gmail_client.create_draft(
            to="alice@example.com",
            subject="Test Draft",
            body="Hello, Alice!",
        )

    assert isinstance(draft, EmailDraft)
    assert draft.id == "draft_xyz"
    assert draft.to == "alice@example.com"
    assert draft.subject == "Test Draft"
    assert draft.body == "Hello, Alice!"


@pytest.mark.asyncio
async def test_create_draft_nested_id(gmail_client):
    """create_draft extracts id from draft.id when top-level id is absent."""
    from integrations.google.gmail_client import EmailDraft

    canned = {"draft": {"id": "nested_draft_id"}}
    with patch(
        "integrations.google.gmail_client.run_gog",
        new=AsyncMock(return_value=canned),
    ):
        draft = await gmail_client.create_draft(
            to="bob@example.com", subject="S", body="B"
        )

    assert draft.id == "nested_draft_id"


@pytest.mark.asyncio
async def test_create_draft_empty_to_raises_immediately(gmail_client):
    """create_draft raises GmailClientError without calling gog when to is empty."""
    from integrations.google.gmail_client import GmailClientError

    mock_run = AsyncMock()
    with patch("integrations.google.gmail_client.run_gog", new=mock_run):
        with pytest.raises(GmailClientError):
            await gmail_client.create_draft(to="", subject="Test", body="Body")

    mock_run.assert_not_called()


@pytest.mark.asyncio
async def test_create_draft_whitespace_only_to_raises(gmail_client):
    """create_draft raises GmailClientError when to is only whitespace."""
    from integrations.google.gmail_client import GmailClientError

    with patch("integrations.google.gmail_client.run_gog", new=AsyncMock()):
        with pytest.raises(GmailClientError):
            await gmail_client.create_draft(to="   ", subject="Test", body="Body")


@pytest.mark.asyncio
async def test_create_draft_no_id_uses_placeholder(gmail_client):
    """create_draft falls back to a placeholder id when gog returns no id."""
    with patch(
        "integrations.google.gmail_client.run_gog",
        new=AsyncMock(return_value={}),
    ):
        draft = await gmail_client.create_draft(
            to="x@example.com", subject="S", body="B"
        )

    assert "x@example.com" in draft.id or "unknown" in draft.id


# ---------------------------------------------------------------------------
# GmailClient.send_draft (AC #3)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_draft_returns_message_id(gmail_client):
    """send_draft returns the sent message id from gog response."""
    canned = {"id": "sent_msg_001"}
    with patch(
        "integrations.google.gmail_client.run_gog",
        new=AsyncMock(return_value=canned),
    ):
        message_id = await gmail_client.send_draft("draft_abc")

    assert message_id == "sent_msg_001"


@pytest.mark.asyncio
async def test_send_draft_falls_back_to_draft_id_on_empty_response(gmail_client):
    """send_draft returns the draft_id when gog response has no id."""
    with patch(
        "integrations.google.gmail_client.run_gog",
        new=AsyncMock(return_value={}),
    ):
        result = await gmail_client.send_draft("draft_fallback")

    assert result == "draft_fallback"


# ---------------------------------------------------------------------------
# GmailClient.delete_draft (AC #3)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_draft_returns_true_on_success(gmail_client):
    """delete_draft returns True when gog succeeds."""
    with patch(
        "integrations.google.gmail_client.run_gog",
        new=AsyncMock(return_value={}),
    ):
        result = await gmail_client.delete_draft("draft_ok")

    assert result is True


@pytest.mark.asyncio
async def test_delete_draft_returns_false_on_failure(gmail_client):
    """delete_draft returns False (non-fatal) when gog raises."""
    from integrations.google.gmail_client import GmailClientError

    with patch(
        "integrations.google.gmail_client.run_gog",
        new=AsyncMock(side_effect=GmailClientError("not found")),
    ):
        result = await gmail_client.delete_draft("bad_draft")

    assert result is False


# ---------------------------------------------------------------------------
# Error propagation (AC #4)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gog_command_error_raises_gmail_client_error(gmail_client):
    """GogCommandError from run_gog is wrapped as GmailClientError."""
    from integrations.google.gmail_client import GmailClientError
    from integrations.openclaw.client import GogCommandError

    with patch(
        "integrations.google.gmail_client.run_gog",
        new=AsyncMock(side_effect=GogCommandError("exit 1", "Google nicht erreichbar.")),
    ):
        with pytest.raises(GmailClientError) as exc_info:
            await gmail_client.list_unread()

    assert exc_info.value.spoken_message


@pytest.mark.asyncio
async def test_gog_not_installed_raises_gmail_client_error(gmail_client):
    """GogNotInstalledError from run_gog is wrapped as GmailClientError."""
    from integrations.google.gmail_client import GmailClientError
    from integrations.openclaw.client import GogNotInstalledError

    with patch(
        "integrations.google.gmail_client.run_gog",
        new=AsyncMock(side_effect=GogNotInstalledError("gog not found")),
    ):
        with pytest.raises(GmailClientError) as exc_info:
            await gmail_client.get_unread_count()

    assert "gog" in exc_info.value.spoken_message.lower() or exc_info.value.spoken_message


@pytest.mark.asyncio
async def test_gog_command_error_in_create_draft_raises(gmail_client):
    """GogCommandError during draft creation raises GmailClientError."""
    from integrations.google.gmail_client import GmailClientError
    from integrations.openclaw.client import GogCommandError

    with patch(
        "integrations.google.gmail_client.run_gog",
        new=AsyncMock(side_effect=GogCommandError("quota exceeded")),
    ):
        with pytest.raises(GmailClientError):
            await gmail_client.create_draft("to@example.com", "Subj", "Body")


@pytest.mark.asyncio
async def test_gog_not_installed_in_send_draft_raises(gmail_client):
    """GogNotInstalledError during draft send raises GmailClientError."""
    from integrations.google.gmail_client import GmailClientError
    from integrations.openclaw.client import GogNotInstalledError

    with patch(
        "integrations.google.gmail_client.run_gog",
        new=AsyncMock(side_effect=GogNotInstalledError("no gog")),
    ):
        with pytest.raises(GmailClientError):
            await gmail_client.send_draft("draft_xyz")


# ---------------------------------------------------------------------------
# Account args
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_account_args_included_when_set():
    """When account is configured, --account is passed to gog."""
    from integrations.google.gmail_client import GmailClient

    client = GmailClient(account="user@gmail.com", vip_senders=[], timeout_seconds=5.0)
    captured: list[tuple] = []

    async def capture_run(*args: str, **kwargs: Any) -> dict:
        captured.append(args)
        return {"messages": []}

    with patch("integrations.google.gmail_client.run_gog", side_effect=capture_run):
        await client.list_unread()

    assert "--account" in captured[0]
    idx = captured[0].index("--account")
    assert captured[0][idx + 1] == "user@gmail.com"


@pytest.mark.asyncio
async def test_no_account_args_when_account_is_none(gmail_client):
    """When account is None, --account is NOT passed to gog."""
    captured: list[tuple] = []

    async def capture_run(*args: str, **kwargs: Any) -> dict:
        captured.append(args)
        return {"messages": []}

    with patch("integrations.google.gmail_client.run_gog", side_effect=capture_run):
        await gmail_client.list_unread()

    assert "--account" not in captured[0]


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------


def test_get_gmail_client_singleton():
    """get_gmail_client() returns the same instance on repeated calls."""
    import integrations.google.gmail_client as _mod

    original = _mod._gmail_client_instance
    _mod._gmail_client_instance = None

    try:
        with patch("utils.config_loader.get_config") as mock_cfg:
            cfg = MagicMock()
            cfg.get_section.return_value = {}
            mock_cfg.return_value = cfg

            c1 = _mod.get_gmail_client()
            c2 = _mod.get_gmail_client()
            assert c1 is c2
    finally:
        _mod._gmail_client_instance = original


def test_get_gmail_client_creates_new_after_reset():
    """After singleton is cleared, a new instance is created."""
    import integrations.google.gmail_client as _mod

    original = _mod._gmail_client_instance
    _mod._gmail_client_instance = None

    try:
        with patch("utils.config_loader.get_config") as mock_cfg:
            cfg = MagicMock()
            cfg.get_section.return_value = {}
            mock_cfg.return_value = cfg

            c1 = _mod.get_gmail_client()
            _mod._gmail_client_instance = None
            c2 = _mod.get_gmail_client()
            assert c1 is not c2
    finally:
        _mod._gmail_client_instance = original
