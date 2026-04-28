"""Tests for WikiClient — async read-only bridge to OpenClaw's memory-wiki RPC.

Covers every public method (search, get, status, obsidian_open) plus error
mapping (_RPC_TIMEOUT_S, bad response shapes, generic exceptions).  All
external I/O is mocked; no live OpenClaw gateway is required.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from integrations.openclaw.wiki_client import (
    WikiClient,
    WikiClientUnavailableError,
    WikiHit,
    WikiNote,
    WikiStatus,
    _RPC_TIMEOUT_S,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ws_client(is_connected: bool = True) -> MagicMock:
    """Return a stub OpenClawWSClient with a call_rpc AsyncMock."""
    ws = MagicMock()
    ws.is_connected = is_connected
    ws.connect = AsyncMock()
    ws.call_rpc = AsyncMock()
    return ws


def _make_client(is_connected: bool = True) -> tuple[WikiClient, MagicMock]:
    """Return (WikiClient, stub_ws_client) pair."""
    ws = _make_ws_client(is_connected=is_connected)
    client = WikiClient(ws)
    return client, ws


# Typical OpenClaw wiki.search response payload.
_SAMPLE_SEARCH_PAYLOAD = [
    {
        "id": "notes/sister",
        "path": "notes/sister",
        "title": "Schwester",
        "score": 0.92,
        "snippet": "Geburtstag am 12. Juni.",
        "updatedAt": "2025-01-15T10:00:00Z",
    },
    {
        "id": "notes/family",
        "path": "notes/family",
        "title": "Familie",
        "score": 0.80,
        "snippet": "Familie details.",
        "updatedAt": "2025-01-10T08:00:00Z",
    },
]

# Typical OpenClaw wiki.get response payload.
_SAMPLE_NOTE_PAYLOAD = {
    "id": "notes/sister",
    "path": "notes/sister",
    "title": "Schwester",
    "content": "# Schwester\n\nGeburtstag am 12. Juni.",
    "updatedAt": "2025-01-15T10:00:00Z",
}

# Typical wiki.status payload.
_SAMPLE_STATUS_PAYLOAD = {
    "vaultExists": True,
    "vaultPath": "/home/user/Obsidian/jarvis-vault",
    "renderMode": "obsidian",
    "pageCounts": {"notes": 42, "journal": 8},
}


# ---------------------------------------------------------------------------
# WikiClient.search
# ---------------------------------------------------------------------------


class TestWikiClientSearch:
    """Tests for WikiClient.search()."""

    @pytest.mark.asyncio
    async def test_search_happy_path_returns_wiki_hits(self):
        """search() maps RPC list response to list[WikiHit]."""
        client, ws = _make_client()
        ws.call_rpc = AsyncMock(return_value=_SAMPLE_SEARCH_PAYLOAD)

        hits = await client.search("Schwester", k=6)

        assert len(hits) == 2
        assert all(isinstance(h, WikiHit) for h in hits)
        assert hits[0].id == "notes/sister"
        assert hits[0].title == "Schwester"
        assert hits[0].score == 0.92
        assert hits[0].excerpt == "Geburtstag am 12. Juni."
        assert hits[0].updated_at == "2025-01-15T10:00:00Z"

    @pytest.mark.asyncio
    async def test_search_forwards_k_parameter(self):
        """search() passes maxResults=k in the RPC params dict."""
        client, ws = _make_client()
        ws.call_rpc = AsyncMock(return_value=[])

        await client.search("test", k=3)

        ws.call_rpc.assert_awaited_once()
        _, params = ws.call_rpc.call_args[0]
        assert params["maxResults"] == 3

    @pytest.mark.asyncio
    async def test_search_empty_vault_returns_empty_list(self):
        """search() returns [] when RPC returns empty list."""
        client, ws = _make_client()
        ws.call_rpc = AsyncMock(return_value=[])

        hits = await client.search("nothing here")

        assert hits == []

    @pytest.mark.asyncio
    async def test_search_timeout_raises_unavailable_error(self):
        """asyncio.TimeoutError from call_rpc → WikiClientUnavailableError with method name."""
        client, ws = _make_client()

        async def _slow_rpc(*_a, **_kw):
            await asyncio.sleep(9999)

        ws.call_rpc = _slow_rpc

        with patch(
            "integrations.openclaw.wiki_client.asyncio.wait_for",
            side_effect=asyncio.TimeoutError,
        ):
            with pytest.raises(WikiClientUnavailableError) as exc_info:
                await client.search("test")

        assert "wiki.search" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_search_generic_exception_raises_unavailable_error(self):
        """Generic Exception from call_rpc → WikiClientUnavailableError."""
        client, ws = _make_client()
        ws.call_rpc = AsyncMock(side_effect=RuntimeError("connection reset"))

        with pytest.raises(WikiClientUnavailableError) as exc_info:
            await client.search("test")

        assert "wiki.search" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_search_non_list_result_returns_empty_list(self):
        """If RPC returns a non-list (e.g. dict), search() yields []."""
        client, ws = _make_client()
        ws.call_rpc = AsyncMock(return_value={"error": "unexpected"})

        hits = await client.search("test")

        assert hits == []

    @pytest.mark.asyncio
    async def test_search_rpc_timeout_constant_honored(self):
        """_RPC_TIMEOUT_S is passed to asyncio.wait_for as timeout."""
        client, ws = _make_client()
        ws.call_rpc = AsyncMock(return_value=[])

        timeouts_seen: list[float] = []
        _orig_wait_for = asyncio.wait_for

        async def _capturing_wait_for(coro, timeout=None, **kw):
            timeouts_seen.append(timeout)
            return await _orig_wait_for(coro, timeout=timeout, **kw)

        with patch(
            "integrations.openclaw.wiki_client.asyncio.wait_for",
            side_effect=_capturing_wait_for,
        ):
            await client.search("test")

        assert timeouts_seen and timeouts_seen[0] == _RPC_TIMEOUT_S


# ---------------------------------------------------------------------------
# WikiClient.get
# ---------------------------------------------------------------------------


class TestWikiClientGet:
    """Tests for WikiClient.get()."""

    @pytest.mark.asyncio
    async def test_get_happy_path_returns_wiki_note(self):
        """get() maps RPC dict response to WikiNote with body_md from 'content'."""
        client, ws = _make_client()
        ws.call_rpc = AsyncMock(return_value=_SAMPLE_NOTE_PAYLOAD)

        note = await client.get("notes/sister")

        assert isinstance(note, WikiNote)
        assert note.id == "notes/sister"
        assert note.title == "Schwester"
        assert "Geburtstag" in note.body_md
        assert note.updated_at == "2025-01-15T10:00:00Z"

    @pytest.mark.asyncio
    async def test_get_uses_content_field_as_body_md(self):
        """get() maps the 'content' RPC field to WikiNote.body_md."""
        client, ws = _make_client()
        payload = {
            "id": "my-note",
            "title": "My Note",
            "content": "# Heading\n\nBody text here.",
            "updatedAt": "2025-02-01T00:00:00Z",
        }
        ws.call_rpc = AsyncMock(return_value=payload)

        note = await client.get("my-note")

        assert note.body_md == "# Heading\n\nBody text here."

    @pytest.mark.asyncio
    async def test_get_falls_back_to_path_for_id(self):
        """get() uses 'path' as note id when 'id' is absent from response."""
        client, ws = _make_client()
        payload = {
            "path": "notes/fallback",
            "title": "Fallback",
            "content": "content",
            "updatedAt": "",
        }
        ws.call_rpc = AsyncMock(return_value=payload)

        note = await client.get("notes/fallback")

        assert note.id == "notes/fallback"

    @pytest.mark.asyncio
    async def test_get_non_dict_result_raises_unavailable_error(self):
        """get() raises WikiClientUnavailableError when RPC returns a non-dict."""
        client, ws = _make_client()
        ws.call_rpc = AsyncMock(return_value="this is a string")

        with pytest.raises(WikiClientUnavailableError) as exc_info:
            await client.get("some-note")

        assert "str" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_timeout_raises_unavailable_error(self):
        """asyncio.TimeoutError from call_rpc → WikiClientUnavailableError with method name."""
        client, ws = _make_client()

        with patch(
            "integrations.openclaw.wiki_client.asyncio.wait_for",
            side_effect=asyncio.TimeoutError,
        ):
            with pytest.raises(WikiClientUnavailableError) as exc_info:
                await client.get("test")

        assert "wiki.get" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_generic_exception_raises_unavailable_error(self):
        """Generic Exception from call_rpc → WikiClientUnavailableError."""
        client, ws = _make_client()
        ws.call_rpc = AsyncMock(side_effect=ConnectionError("dropped"))

        with pytest.raises(WikiClientUnavailableError) as exc_info:
            await client.get("test")

        assert "wiki.get" in str(exc_info.value)


# ---------------------------------------------------------------------------
# WikiClient.status
# ---------------------------------------------------------------------------


class TestWikiClientStatus:
    """Tests for WikiClient.status()."""

    @pytest.mark.asyncio
    async def test_status_happy_path_returns_wiki_status(self):
        """status() maps RPC dict to WikiStatus, summing pageCounts."""
        client, ws = _make_client()
        ws.call_rpc = AsyncMock(return_value=_SAMPLE_STATUS_PAYLOAD)

        st = await client.status()

        assert isinstance(st, WikiStatus)
        assert st.initialised is True
        assert st.note_count == 50  # 42 + 8
        assert st.path == "/home/user/Obsidian/jarvis-vault"
        assert st.render_mode == "obsidian"
        assert st.last_dream_cycle_at is None

    @pytest.mark.asyncio
    async def test_status_vault_not_exists_returns_uninitialised(self):
        """status() sets initialised=False when vaultExists is False."""
        client, ws = _make_client()
        payload = {
            "vaultExists": False,
            "vaultPath": "",
            "renderMode": "",
            "pageCounts": {},
        }
        ws.call_rpc = AsyncMock(return_value=payload)

        st = await client.status()

        assert st.initialised is False
        assert st.note_count == 0

    @pytest.mark.asyncio
    async def test_status_sums_all_page_count_categories(self):
        """status() sums all values in pageCounts regardless of category names."""
        client, ws = _make_client()
        payload = {
            "vaultExists": True,
            "vaultPath": "/vault",
            "renderMode": "obsidian",
            "pageCounts": {"notes": 10, "journal": 5, "attachments": 3, "index": 2},
        }
        ws.call_rpc = AsyncMock(return_value=payload)

        st = await client.status()

        assert st.note_count == 20

    @pytest.mark.asyncio
    async def test_status_non_dict_result_raises_unavailable_error(self):
        """status() raises WikiClientUnavailableError when RPC returns non-dict."""
        client, ws = _make_client()
        ws.call_rpc = AsyncMock(return_value=["unexpected", "list"])

        with pytest.raises(WikiClientUnavailableError) as exc_info:
            await client.status()

        assert "list" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_status_timeout_raises_unavailable_error(self):
        """asyncio.TimeoutError from call_rpc → WikiClientUnavailableError."""
        client, ws = _make_client()

        with patch(
            "integrations.openclaw.wiki_client.asyncio.wait_for",
            side_effect=asyncio.TimeoutError,
        ):
            with pytest.raises(WikiClientUnavailableError) as exc_info:
                await client.status()

        assert "wiki.status" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_status_generic_exception_raises_unavailable_error(self):
        """Generic Exception → WikiClientUnavailableError with method name in message."""
        client, ws = _make_client()
        ws.call_rpc = AsyncMock(side_effect=OSError("socket error"))

        with pytest.raises(WikiClientUnavailableError) as exc_info:
            await client.status()

        assert "wiki.status" in str(exc_info.value)


# ---------------------------------------------------------------------------
# WikiClient.obsidian_open
# ---------------------------------------------------------------------------


class TestWikiClientObsidianOpen:
    """Tests for WikiClient.obsidian_open()."""

    @pytest.mark.asyncio
    async def test_obsidian_open_returns_true_on_success(self):
        """obsidian_open() returns True when the RPC call succeeds."""
        client, ws = _make_client()
        ws.call_rpc = AsyncMock(return_value={"ok": True})

        result = await client.obsidian_open("notes/sister")

        assert result is True

    @pytest.mark.asyncio
    async def test_obsidian_open_timeout_raises_unavailable_error(self):
        """asyncio.TimeoutError → WikiClientUnavailableError with method name."""
        client, ws = _make_client()

        with patch(
            "integrations.openclaw.wiki_client.asyncio.wait_for",
            side_effect=asyncio.TimeoutError,
        ):
            with pytest.raises(WikiClientUnavailableError) as exc_info:
                await client.obsidian_open("test")

        assert "wiki.obsidian.open" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_obsidian_open_generic_exception_raises_unavailable_error(self):
        """Generic Exception → WikiClientUnavailableError."""
        client, ws = _make_client()
        ws.call_rpc = AsyncMock(side_effect=RuntimeError("Obsidian not running"))

        with pytest.raises(WikiClientUnavailableError) as exc_info:
            await client.obsidian_open("some/note")

        assert "wiki.obsidian.open" in str(exc_info.value)


# ---------------------------------------------------------------------------
# WikiClient._call — connection handling
# ---------------------------------------------------------------------------


class TestWikiClientCallConnectionHandling:
    """Tests for _call connection auto-connect behaviour."""

    @pytest.mark.asyncio
    async def test_call_auto_connects_when_not_connected(self):
        """_call() calls ws_client.connect() when is_connected is False."""
        client, ws = _make_client(is_connected=False)
        ws.connect = AsyncMock()
        ws.call_rpc = AsyncMock(return_value=[])

        await client.search("test")

        ws.connect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_call_skips_connect_when_already_connected(self):
        """_call() does not call connect() when is_connected is already True."""
        client, ws = _make_client(is_connected=True)
        ws.connect = AsyncMock()
        ws.call_rpc = AsyncMock(return_value=[])

        await client.search("test")

        ws.connect.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_call_connect_failure_raises_unavailable_error(self):
        """If connect() raises, _call() raises WikiClientUnavailableError."""
        client, ws = _make_client(is_connected=False)
        ws.connect = AsyncMock(side_effect=ConnectionRefusedError("refused"))

        with pytest.raises(WikiClientUnavailableError) as exc_info:
            await client.search("test")

        assert "Cannot connect" in str(exc_info.value)
