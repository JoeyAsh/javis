"""Tests for the three aiohttp wiki REST handlers in api.ws_server.

Covers:
- GET /api/brain/wiki/search  (AC #7 — HTTP 200, 400, 503)
- GET /api/brain/wiki/note/{note_id}  (AC #8 — HTTP 200, 404, 503)
- POST /api/brain/wiki/obsidian-open  (AC #15, #16 — HTTP 200, 400, 503)
- vault_status + last_wiki_search flow into broadcast_brain_inspector (AC #13)

All external I/O is mocked; no live OpenClaw gateway or HTTP server required
for the route handler tests.  Uses aiohttp.test_utils.TestServer + TestClient
following the pattern established by tests/api/test_spotify_routes.py.
"""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

import api.ws_server as mod
from integrations.openclaw.wiki_client import (
    WikiClientUnavailableError,
    WikiHit,
    WikiNote,
    WikiStatus,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_wiki_hit(
    note_id: str = "notes/sister",
    title: str = "Schwester",
    score: float = 0.92,
    excerpt: str = "Geburtstag am 12. Juni.",
    updated_at: str = "2025-01-15T10:00:00Z",
) -> WikiHit:
    return WikiHit(
        id=note_id,
        title=title,
        score=score,
        excerpt=excerpt,
        updated_at=updated_at,
    )


def _make_wiki_note(
    note_id: str = "notes/sister",
    title: str = "Schwester",
    body_md: str = "# Schwester\n\nGeburtstag am 12. Juni.",
    updated_at: str = "2025-01-15T10:00:00Z",
) -> WikiNote:
    return WikiNote(
        id=note_id,
        title=title,
        body_md=body_md,
        backlinks=[],
        updated_at=updated_at,
    )


def _make_wiki_status(
    initialised: bool = True,
    note_count: int = 42,
    path: str = "/home/user/Obsidian/jarvis-vault",
    render_mode: str = "obsidian",
) -> WikiStatus:
    return WikiStatus(
        initialised=initialised,
        note_count=note_count,
        last_dream_cycle_at=None,
        path=path,
        render_mode=render_mode,
    )


def _make_mock_wiki_client(
    search_return: list[WikiHit] | None = None,
    get_return: WikiNote | None = None,
    status_return: WikiStatus | None = None,
) -> MagicMock:
    """Return a MagicMock shaped like WikiClient."""
    mock = MagicMock()
    mock.search = AsyncMock(return_value=search_return or [])
    mock.get = AsyncMock(return_value=get_return or _make_wiki_note())
    mock.status = AsyncMock(return_value=status_return or _make_wiki_status())
    mock.obsidian_open = AsyncMock(return_value=True)
    return mock


async def _build_wiki_app() -> web.Application:
    """Build a minimal aiohttp app with only wiki route handlers."""
    from api.ws_server import (
        wiki_note_handler,
        wiki_obsidian_open_handler,
        wiki_search_handler,
    )

    app = web.Application()
    app.router.add_get("/api/brain/wiki/search", wiki_search_handler)
    app.router.add_get("/api/brain/wiki/note/{note_id}", wiki_note_handler)
    app.router.add_post("/api/brain/wiki/obsidian-open", wiki_obsidian_open_handler)
    return app


@asynccontextmanager
async def _client_ctx(wiki_client: MagicMock | None, last_wiki_search: dict | None = None):
    """Spin up TestClient patching _wiki_client and _last_wiki_search on the module."""
    app = await _build_wiki_app()
    server = TestServer(app)
    client = TestClient(server)

    with (
        patch.object(mod, "_wiki_client", wiki_client),
        patch.object(mod, "_last_wiki_search", last_wiki_search),
    ):
        await client.start_server()
        try:
            yield client
        finally:
            await client.close()


# ---------------------------------------------------------------------------
# GET /api/brain/wiki/search
# ---------------------------------------------------------------------------


class TestWikiSearchHandler:
    """Tests for GET /api/brain/wiki/search."""

    @pytest.mark.asyncio
    async def test_search_happy_path_returns_200_with_hits(self):
        """Happy path: returns 200 with non-empty hits array."""
        hit = _make_wiki_hit()
        mock_client = _make_mock_wiki_client(search_return=[hit])

        async with _client_ctx(mock_client) as client:
            resp = await client.get("/api/brain/wiki/search?q=test")
            assert resp.status == 200
            body = await resp.json()
            assert "hits" in body
            assert len(body["hits"]) == 1
            assert body["hits"][0]["id"] == "notes/sister"
            assert body["hits"][0]["title"] == "Schwester"
            assert body["hits"][0]["score"] == 0.92

    @pytest.mark.asyncio
    async def test_search_missing_q_returns_400(self):
        """Missing 'q' parameter returns 400."""
        mock_client = _make_mock_wiki_client()

        async with _client_ctx(mock_client) as client:
            resp = await client.get("/api/brain/wiki/search")
            assert resp.status == 400
            body = await resp.json()
            assert "error" in body

    @pytest.mark.asyncio
    async def test_search_empty_q_returns_400(self):
        """Blank 'q' parameter (whitespace only) returns 400."""
        mock_client = _make_mock_wiki_client()

        async with _client_ctx(mock_client) as client:
            resp = await client.get("/api/brain/wiki/search?q=   ")
            assert resp.status == 400

    @pytest.mark.asyncio
    async def test_search_wiki_client_none_returns_503(self):
        """_wiki_client is None → 503."""
        async with _client_ctx(None) as client:
            resp = await client.get("/api/brain/wiki/search?q=test")
            assert resp.status == 503

    @pytest.mark.asyncio
    async def test_search_wiki_unavailable_error_returns_503(self):
        """WikiClientUnavailableError from search() → 503."""
        mock_client = _make_mock_wiki_client()
        mock_client.search = AsyncMock(
            side_effect=WikiClientUnavailableError("connection lost")
        )

        async with _client_ctx(mock_client) as client:
            resp = await client.get("/api/brain/wiki/search?q=test")
            assert resp.status == 503

    @pytest.mark.asyncio
    async def test_search_updates_last_wiki_search_on_success(self):
        """Successful search sets _last_wiki_search with query, hit_count, ts."""
        hit = _make_wiki_hit()
        mock_client = _make_mock_wiki_client(search_return=[hit])

        # Save and reset _last_wiki_search to None before request.
        saved = mod._last_wiki_search
        mod._last_wiki_search = None
        try:
            app = await _build_wiki_app()
            server = TestServer(app)
            http_client = TestClient(server)

            with patch.object(mod, "_wiki_client", mock_client):
                await http_client.start_server()
                try:
                    await http_client.get("/api/brain/wiki/search?q=Schwester")
                finally:
                    await http_client.close()

            # _last_wiki_search should now be set.
            assert mod._last_wiki_search is not None
            assert mod._last_wiki_search["query"] == "Schwester"
            assert mod._last_wiki_search["hit_count"] == 1
            assert "ts" in mod._last_wiki_search
        finally:
            # Restore original value.
            mod._last_wiki_search = saved

    @pytest.mark.asyncio
    async def test_search_last_wiki_search_not_updated_on_error(self):
        """Failed search does NOT update _last_wiki_search."""
        mock_client = _make_mock_wiki_client()
        mock_client.search = AsyncMock(side_effect=WikiClientUnavailableError("nope"))

        original_last = {"query": "old", "hit_count": 0, "ts": "old-ts"}

        saved = mod._last_wiki_search
        mod._last_wiki_search = original_last
        try:
            app = await _build_wiki_app()
            server = TestServer(app)
            http_client = TestClient(server)
            with patch.object(mod, "_wiki_client", mock_client):
                await http_client.start_server()
                try:
                    await http_client.get("/api/brain/wiki/search?q=test")
                finally:
                    await http_client.close()

            # _last_wiki_search should still be the original (unchanged).
            assert mod._last_wiki_search == original_last
        finally:
            mod._last_wiki_search = saved

    @pytest.mark.asyncio
    async def test_search_k_parameter_clamped_to_valid_range(self):
        """k is clamped to [1, 20]; handler still returns 200."""
        mock_client = _make_mock_wiki_client(search_return=[])

        async with _client_ctx(mock_client) as client:
            resp = await client.get("/api/brain/wiki/search?q=test&k=100")
            assert resp.status == 200
            # k was clamped — search was still called.
            mock_client.search.assert_awaited_once()
            call_args = mock_client.search.call_args
            # k may be a positional or keyword argument.
            positional_args = call_args[0] if call_args[0] else ()
            keyword_args = call_args[1] if call_args[1] else {}
            if len(positional_args) >= 2:
                k_arg = positional_args[1]
            else:
                k_arg = keyword_args.get("k", None)
            # k should be clamped to 20
            assert k_arg is not None
            assert k_arg <= 20

    @pytest.mark.asyncio
    async def test_search_invalid_k_defaults_to_6(self):
        """Non-numeric k falls back to 6."""
        mock_client = _make_mock_wiki_client(search_return=[])

        async with _client_ctx(mock_client) as client:
            resp = await client.get("/api/brain/wiki/search?q=test&k=notanumber")
            assert resp.status == 200


# ---------------------------------------------------------------------------
# GET /api/brain/wiki/note/{note_id}
# ---------------------------------------------------------------------------


class TestWikiNoteHandler:
    """Tests for GET /api/brain/wiki/note/{note_id}."""

    @pytest.mark.asyncio
    async def test_note_happy_path_returns_200_with_note(self):
        """Happy path: returns 200 with full note body."""
        note = _make_wiki_note()
        mock_client = _make_mock_wiki_client(get_return=note)

        async with _client_ctx(mock_client) as client:
            resp = await client.get("/api/brain/wiki/note/notes%2Fsister")
            assert resp.status == 200
            body = await resp.json()
            assert body["id"] == "notes/sister"
            assert body["title"] == "Schwester"
            assert "Geburtstag" in body["body_md"]

    @pytest.mark.asyncio
    async def test_note_wiki_client_none_returns_503(self):
        """_wiki_client is None → 503."""
        async with _client_ctx(None) as client:
            resp = await client.get("/api/brain/wiki/note/some-note")
            assert resp.status == 503

    @pytest.mark.asyncio
    async def test_note_not_found_returns_404(self):
        """WikiClientUnavailableError with 'not found' in message → 404."""
        mock_client = _make_mock_wiki_client()
        mock_client.get = AsyncMock(
            side_effect=WikiClientUnavailableError("Note not found in vault")
        )

        async with _client_ctx(mock_client) as client:
            resp = await client.get("/api/brain/wiki/note/missing")
            assert resp.status == 404

    @pytest.mark.asyncio
    async def test_note_other_unavailable_error_returns_503(self):
        """WikiClientUnavailableError without 'not found' → 503."""
        mock_client = _make_mock_wiki_client()
        mock_client.get = AsyncMock(
            side_effect=WikiClientUnavailableError("connection reset")
        )

        async with _client_ctx(mock_client) as client:
            resp = await client.get("/api/brain/wiki/note/some-note")
            assert resp.status == 503

    @pytest.mark.asyncio
    async def test_note_response_includes_required_fields(self):
        """Response JSON includes id, title, body_md, backlinks, updated_at."""
        note = _make_wiki_note()
        mock_client = _make_mock_wiki_client(get_return=note)

        async with _client_ctx(mock_client) as client:
            resp = await client.get("/api/brain/wiki/note/notes%2Fsister")
            body = await resp.json()

        for field in ("id", "title", "body_md", "backlinks", "updated_at"):
            assert field in body, f"Missing field: {field}"


# ---------------------------------------------------------------------------
# POST /api/brain/wiki/obsidian-open
# ---------------------------------------------------------------------------


class TestWikiObsidianOpenHandler:
    """Tests for POST /api/brain/wiki/obsidian-open."""

    @pytest.mark.asyncio
    async def test_obsidian_open_happy_path_returns_200_ok(self):
        """Happy path: returns 200 with {ok: true}."""
        mock_client = _make_mock_wiki_client()

        async with _client_ctx(mock_client) as client:
            resp = await client.post(
                "/api/brain/wiki/obsidian-open",
                json={"note_id": "notes/sister"},
            )
            assert resp.status == 200
            body = await resp.json()
            assert body["ok"] is True

    @pytest.mark.asyncio
    async def test_obsidian_open_missing_note_id_returns_400(self):
        """Missing note_id in body → 400."""
        mock_client = _make_mock_wiki_client()

        async with _client_ctx(mock_client) as client:
            resp = await client.post(
                "/api/brain/wiki/obsidian-open",
                json={},
            )
            assert resp.status == 400

    @pytest.mark.asyncio
    async def test_obsidian_open_empty_note_id_returns_400(self):
        """Blank note_id in body → 400."""
        mock_client = _make_mock_wiki_client()

        async with _client_ctx(mock_client) as client:
            resp = await client.post(
                "/api/brain/wiki/obsidian-open",
                json={"note_id": "   "},
            )
            assert resp.status == 400

    @pytest.mark.asyncio
    async def test_obsidian_open_wiki_client_none_returns_503(self):
        """_wiki_client is None → 503."""
        async with _client_ctx(None) as client:
            resp = await client.post(
                "/api/brain/wiki/obsidian-open",
                json={"note_id": "notes/sister"},
            )
            assert resp.status == 503

    @pytest.mark.asyncio
    async def test_obsidian_open_unavailable_error_returns_503(self):
        """WikiClientUnavailableError from obsidian_open() → 503."""
        mock_client = _make_mock_wiki_client()
        mock_client.obsidian_open = AsyncMock(
            side_effect=WikiClientUnavailableError("Obsidian not running")
        )

        async with _client_ctx(mock_client) as client:
            resp = await client.post(
                "/api/brain/wiki/obsidian-open",
                json={"note_id": "notes/sister"},
            )
            assert resp.status == 503

    @pytest.mark.asyncio
    async def test_obsidian_open_invalid_json_body_returns_400(self):
        """Malformed JSON body → 400."""
        mock_client = _make_mock_wiki_client()

        async with _client_ctx(mock_client) as client:
            resp = await client.post(
                "/api/brain/wiki/obsidian-open",
                data=b"not-json",
                headers={"Content-Type": "application/json"},
            )
            assert resp.status == 400


# ---------------------------------------------------------------------------
# broadcast_brain_inspector — vault_status and last_wiki_search
# (AC #13: verifies fields flow into the payload)
# ---------------------------------------------------------------------------


class _FakeWs:
    """Minimal WebSocket stand-in that captures sent messages."""

    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send_str(self, message: str) -> None:
        self.sent.append(message)


class TestBrainInspectorWikiFields:
    """Verify vault_status + last_wiki_search appear in brain_inspector payload."""

    @pytest.mark.asyncio
    async def test_brain_inspector_includes_vault_status_key(self):
        """broadcast_brain_inspector() payload always has a 'vault_status' key."""
        from brain.device_ledger import DeviceLedger
        from brain.voice_composer import VoiceComposer
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            db_file = str(Path(td) / "bi_wiki.db")
            dl = DeviceLedger(db_path=db_file)
            await dl.init()
            vc = VoiceComposer(config={})

            fake_ws = _FakeWs()
            mod._connected_clients.add(fake_ws)

            try:
                with (
                    patch.object(mod, "_voice_composer", vc),
                    patch.object(mod, "_device_ledger", dl),
                    patch.object(mod, "_wiki_client", None),
                    patch.object(mod, "_last_wiki_search", None),
                ):
                    await mod.broadcast_brain_inspector()
            finally:
                mod._connected_clients.discard(fake_ws)

        assert len(fake_ws.sent) == 1
        payload = json.loads(fake_ws.sent[0])["payload"]
        assert "vault_status" in payload
        assert payload["vault_status"] is None  # _wiki_client is None

    @pytest.mark.asyncio
    async def test_brain_inspector_vault_status_populated_from_wiki_client(self):
        """vault_status is populated when WikiClient.status() returns successfully."""
        from brain.device_ledger import DeviceLedger
        from brain.voice_composer import VoiceComposer
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            db_file = str(Path(td) / "bi_wiki_populated.db")
            dl = DeviceLedger(db_path=db_file)
            await dl.init()
            vc = VoiceComposer(config={})

            mock_wiki = _make_mock_wiki_client(
                status_return=_make_wiki_status(initialised=True, note_count=50)
            )

            fake_ws = _FakeWs()
            mod._connected_clients.add(fake_ws)

            try:
                with (
                    patch.object(mod, "_voice_composer", vc),
                    patch.object(mod, "_device_ledger", dl),
                    patch.object(mod, "_wiki_client", mock_wiki),
                    patch.object(mod, "_last_wiki_search", None),
                ):
                    await mod.broadcast_brain_inspector()
            finally:
                mod._connected_clients.discard(fake_ws)

        payload = json.loads(fake_ws.sent[0])["payload"]
        vs = payload["vault_status"]
        assert vs is not None
        assert vs["initialised"] is True
        assert vs["note_count"] == 50

    @pytest.mark.asyncio
    async def test_brain_inspector_vault_status_none_on_wiki_unavailable(self):
        """vault_status is None when WikiClientUnavailableError is raised."""
        from brain.device_ledger import DeviceLedger
        from brain.voice_composer import VoiceComposer
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            db_file = str(Path(td) / "bi_wiki_unavail.db")
            dl = DeviceLedger(db_path=db_file)
            await dl.init()
            vc = VoiceComposer(config={})

            mock_wiki = MagicMock()
            mock_wiki.status = AsyncMock(
                side_effect=WikiClientUnavailableError("no connection")
            )

            fake_ws = _FakeWs()
            mod._connected_clients.add(fake_ws)

            try:
                with (
                    patch.object(mod, "_voice_composer", vc),
                    patch.object(mod, "_device_ledger", dl),
                    patch.object(mod, "_wiki_client", mock_wiki),
                    patch.object(mod, "_last_wiki_search", None),
                ):
                    await mod.broadcast_brain_inspector()
            finally:
                mod._connected_clients.discard(fake_ws)

        payload = json.loads(fake_ws.sent[0])["payload"]
        assert payload["vault_status"] is None

    @pytest.mark.asyncio
    async def test_brain_inspector_vault_status_none_on_5s_timeout(self):
        """vault_status is None when WikiClient.status() times out (5 s guard)."""
        from brain.device_ledger import DeviceLedger
        from brain.voice_composer import VoiceComposer
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            db_file = str(Path(td) / "bi_wiki_timeout.db")
            dl = DeviceLedger(db_path=db_file)
            await dl.init()
            vc = VoiceComposer(config={})

            mock_wiki = MagicMock()
            # Simulate asyncio.wait_for raising TimeoutError for the status call.
            mock_wiki.status = AsyncMock(side_effect=asyncio.TimeoutError)

            fake_ws = _FakeWs()
            mod._connected_clients.add(fake_ws)

            try:
                with (
                    patch.object(mod, "_voice_composer", vc),
                    patch.object(mod, "_device_ledger", dl),
                    patch.object(mod, "_wiki_client", mock_wiki),
                    patch.object(mod, "_last_wiki_search", None),
                ):
                    await mod.broadcast_brain_inspector()
            finally:
                mod._connected_clients.discard(fake_ws)

        payload = json.loads(fake_ws.sent[0])["payload"]
        assert payload["vault_status"] is None

    @pytest.mark.asyncio
    async def test_brain_inspector_last_wiki_search_reflected_in_payload(self):
        """last_wiki_search state flows into broadcast_brain_inspector payload."""
        from brain.device_ledger import DeviceLedger
        from brain.voice_composer import VoiceComposer
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            db_file = str(Path(td) / "bi_last_search.db")
            dl = DeviceLedger(db_path=db_file)
            await dl.init()
            vc = VoiceComposer(config={})

            last_search = {"query": "Schwester", "hit_count": 2, "ts": "2025-01-15T10:00:00Z"}

            fake_ws = _FakeWs()
            mod._connected_clients.add(fake_ws)

            try:
                with (
                    patch.object(mod, "_voice_composer", vc),
                    patch.object(mod, "_device_ledger", dl),
                    patch.object(mod, "_wiki_client", None),
                    patch.object(mod, "_last_wiki_search", last_search),
                ):
                    await mod.broadcast_brain_inspector()
            finally:
                mod._connected_clients.discard(fake_ws)

        payload = json.loads(fake_ws.sent[0])["payload"]
        assert payload["last_wiki_search"] == last_search
