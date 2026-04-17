"""Tests for transcript archival to MemoryStore.

``broadcast_transcript`` dual-writes every spoken turn to the SQLite
``events`` table so the local JARVIS database keeps an append-only audit
of the voice pipeline (independent of OpenClaw's short-context memory).

Only the archival behaviour is exercised here — the broadcast side is
covered implicitly by the aiohttp-free ``_broadcast`` helper (no
connected clients in the test environment).
"""

from __future__ import annotations

import pytest
import pytest_asyncio

from api import ws_server
from brain.memory import MemoryStore


@pytest_asyncio.fixture
async def memory_store():
    """In-memory ``MemoryStore`` bound to the ``ws_server`` global.

    Restores the pre-existing global on teardown so other tests don't
    observe this wiring.
    """
    store = MemoryStore(db_path=":memory:")
    await store.initialize()

    previous = ws_server._memory_store
    ws_server._memory_store = store

    try:
        yield store
    finally:
        ws_server._memory_store = previous
        await store.close()


class TestBroadcastTranscriptArchival:
    """``broadcast_transcript`` writes an event per turn."""

    @pytest.mark.asyncio
    async def test_user_turn_is_archived(self, memory_store: MemoryStore):
        await ws_server.broadcast_transcript("user", "Hey JARVIS, status?")

        events = await memory_store.get_events(event_type="transcript")

        assert len(events) == 1
        assert events[0].type == "transcript"
        assert events[0].source == "voice"
        assert events[0].payload == {
            "role": "user",
            "text": "Hey JARVIS, status?",
        }

    @pytest.mark.asyncio
    async def test_jarvis_turn_is_archived(self, memory_store: MemoryStore):
        await ws_server.broadcast_transcript("jarvis", "All systems nominal, sir.")

        events = await memory_store.get_events(event_type="transcript")

        assert len(events) == 1
        assert events[0].payload["role"] == "jarvis"
        assert events[0].payload["text"] == "All systems nominal, sir."

    @pytest.mark.asyncio
    async def test_multiple_turns_are_archived(
        self, memory_store: MemoryStore
    ):
        """All turns land as distinct ``transcript`` events."""
        await ws_server.broadcast_transcript("user", "Lights on")
        await ws_server.broadcast_transcript("jarvis", "Done, sir.")
        await ws_server.broadcast_transcript("user", "And the thermostat")

        events = await memory_store.get_events(event_type="transcript")

        assert len(events) == 3
        texts = {e.payload["text"] for e in events}
        assert texts == {"Lights on", "Done, sir.", "And the thermostat"}
        assert all(e.source == "voice" for e in events)

    @pytest.mark.asyncio
    async def test_archive_disabled_when_memory_store_absent(self):
        """Without a MemoryStore the broadcast must still succeed silently."""
        previous = ws_server._memory_store
        ws_server._memory_store = None
        try:
            # Must not raise; only the broadcast path is exercised.
            await ws_server.broadcast_transcript("user", "floating turn")
        finally:
            ws_server._memory_store = previous
