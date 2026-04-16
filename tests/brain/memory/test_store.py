"""Unit tests for MemoryStore.

Tests cover:
- Database initialization and connection
- Conversation turn storage and retrieval
- FTS5 search functionality
- Preference get/set/delete
- Event logging and querying
"""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio

from brain.memory import ConversationTurn, Event, MemoryStore


@pytest.fixture
def temp_db_path():
    """Provide a temporary database path for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield str(Path(tmpdir) / "test_jarvis.db")


@pytest_asyncio.fixture
async def memory_store(temp_db_path):
    """Provide an initialized MemoryStore instance."""
    store = MemoryStore(temp_db_path)
    await store.initialize()
    yield store
    await store.close()


class TestMemoryStoreInitialization:
    """Tests for MemoryStore initialization and connection."""

    @pytest.mark.asyncio
    async def test_initialize_creates_database(self, temp_db_path):
        """Test that initialize() creates the database file."""
        store = MemoryStore(temp_db_path)
        assert not Path(temp_db_path).exists()

        await store.initialize()

        assert Path(temp_db_path).exists()
        assert store.is_connected
        await store.close()

    @pytest.mark.asyncio
    async def test_initialize_creates_directory(self):
        """Test that initialize() creates parent directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "nested" / "dir" / "test.db")
            store = MemoryStore(db_path)

            await store.initialize()

            assert Path(db_path).exists()
            await store.close()

    @pytest.mark.asyncio
    async def test_close_disconnects(self, temp_db_path):
        """Test that close() properly disconnects."""
        store = MemoryStore(temp_db_path)
        await store.initialize()
        assert store.is_connected

        await store.close()

        assert not store.is_connected

    @pytest.mark.asyncio
    async def test_close_is_idempotent(self, temp_db_path):
        """Test that close() can be called multiple times."""
        store = MemoryStore(temp_db_path)
        await store.initialize()

        await store.close()
        await store.close()  # Should not raise

        assert not store.is_connected


class TestConversationStorage:
    """Tests for conversation turn storage and retrieval."""

    @pytest.mark.asyncio
    async def test_remember_turn_stores_user_turn(self, memory_store):
        """Test storing a user turn."""
        turn_id = await memory_store.remember_turn(
            session_id="test-session",
            turn_index=0,
            role="user",
            text="Hello JARVIS",
            lang="en",
        )

        assert turn_id == 1

    @pytest.mark.asyncio
    async def test_remember_turn_stores_jarvis_turn(self, memory_store):
        """Test storing a JARVIS turn."""
        turn_id = await memory_store.remember_turn(
            session_id="test-session",
            turn_index=1,
            role="jarvis",
            text="Hello, Sir. How may I assist?",
            lang="en",
        )

        assert turn_id == 1

    @pytest.mark.asyncio
    async def test_remember_turn_rejects_invalid_role(self, memory_store):
        """Test that invalid roles are rejected."""
        with pytest.raises(ValueError, match="Invalid role"):
            await memory_store.remember_turn(
                session_id="test-session",
                turn_index=0,
                role="invalid",
                text="Test",
            )

    @pytest.mark.asyncio
    async def test_remember_turn_with_intent_tag(self, memory_store):
        """Test storing a turn with intent tag."""
        await memory_store.remember_turn(
            session_id="test-session",
            turn_index=0,
            role="user",
            text="Turn on the lights",
            intent_tag="smart_home",
            lang="en",
        )

        turns = await memory_store.get_recent_turns(session_id="test-session")
        assert turns[0].intent_tag == "smart_home"

    @pytest.mark.asyncio
    async def test_get_recent_turns_returns_newest_first(self, memory_store):
        """Test that recent turns are returned newest first (by ID when timestamps equal)."""
        for i in range(5):
            await memory_store.remember_turn(
                session_id="test-session",
                turn_index=i,
                role="user" if i % 2 == 0 else "jarvis",
                text=f"Turn {i}",
            )

        turns = await memory_store.get_recent_turns(session_id="test-session")

        assert len(turns) == 5
        # With rapid inserts, timestamps may be identical, so we order by ID DESC
        # This means the last inserted (highest ID) comes first
        turn_texts = [t.text for t in turns]
        # Verify all turns are present
        assert set(turn_texts) == {f"Turn {i}" for i in range(5)}
        # The turn with highest ID (Turn 4) should be first
        assert turns[0].id > turns[4].id

    @pytest.mark.asyncio
    async def test_get_recent_turns_respects_limit(self, memory_store):
        """Test that limit parameter is respected."""
        for i in range(10):
            await memory_store.remember_turn(
                session_id="test-session",
                turn_index=i,
                role="user",
                text=f"Turn {i}",
            )

        turns = await memory_store.get_recent_turns(session_id="test-session", limit=3)

        assert len(turns) == 3

    @pytest.mark.asyncio
    async def test_get_recent_turns_filters_by_session(self, memory_store):
        """Test filtering by session ID."""
        await memory_store.remember_turn(
            session_id="session-a", turn_index=0, role="user", text="Session A"
        )
        await memory_store.remember_turn(
            session_id="session-b", turn_index=0, role="user", text="Session B"
        )

        turns_a = await memory_store.get_recent_turns(session_id="session-a")
        turns_b = await memory_store.get_recent_turns(session_id="session-b")

        assert len(turns_a) == 1
        assert turns_a[0].text == "Session A"
        assert len(turns_b) == 1
        assert turns_b[0].text == "Session B"


class TestFTS5Search:
    """Tests for full-text search functionality."""

    @pytest.mark.asyncio
    async def test_recall_finds_matching_turn(self, memory_store):
        """Test that recall finds matching conversations."""
        await memory_store.remember_turn(
            session_id="test", turn_index=0, role="user", text="What is the weather today"
        )
        await memory_store.remember_turn(
            session_id="test", turn_index=1, role="jarvis", text="It's sunny and warm"
        )

        results = await memory_store.recall("weather")

        assert len(results) == 1
        assert "weather" in results[0].text.lower()

    @pytest.mark.asyncio
    async def test_recall_respects_limit(self, memory_store):
        """Test that recall respects limit parameter."""
        for i in range(5):
            await memory_store.remember_turn(
                session_id="test",
                turn_index=i,
                role="user",
                text=f"Question about weather number {i}",
            )

        results = await memory_store.recall("weather", limit=2)

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_recall_returns_empty_for_no_match(self, memory_store):
        """Test that recall returns empty list when no matches."""
        await memory_store.remember_turn(
            session_id="test", turn_index=0, role="user", text="Hello JARVIS"
        )

        results = await memory_store.recall("nonexistent")

        assert results == []

    @pytest.mark.asyncio
    async def test_recall_returns_conversation_turn_type(self, memory_store):
        """Test that recall returns ConversationTurn objects."""
        await memory_store.remember_turn(
            session_id="test", turn_index=0, role="user", text="Weather forecast"
        )

        results = await memory_store.recall("forecast")

        assert len(results) == 1
        assert isinstance(results[0], ConversationTurn)


class TestPreferences:
    """Tests for preference storage and retrieval."""

    @pytest.mark.asyncio
    async def test_pref_set_and_get_string(self, memory_store):
        """Test storing and retrieving a string preference."""
        await memory_store.pref_set("theme", "dark")

        value = await memory_store.pref_get("theme")

        assert value == "dark"

    @pytest.mark.asyncio
    async def test_pref_set_and_get_dict(self, memory_store):
        """Test storing and retrieving a dict preference."""
        layout = {"left": ["transcript"], "right": ["status"]}
        await memory_store.pref_set("panel_layout", layout)

        value = await memory_store.pref_get("panel_layout")

        assert value == layout

    @pytest.mark.asyncio
    async def test_pref_set_and_get_list(self, memory_store):
        """Test storing and retrieving a list preference."""
        voices = ["jarvis", "friday"]
        await memory_store.pref_set("available_voices", voices)

        value = await memory_store.pref_get("available_voices")

        assert value == voices

    @pytest.mark.asyncio
    async def test_pref_get_returns_default(self, memory_store):
        """Test that pref_get returns default for missing key."""
        value = await memory_store.pref_get("nonexistent", default="fallback")

        assert value == "fallback"

    @pytest.mark.asyncio
    async def test_pref_set_overwrites_existing(self, memory_store):
        """Test that pref_set overwrites existing value."""
        await memory_store.pref_set("key", "value1")
        await memory_store.pref_set("key", "value2")

        value = await memory_store.pref_get("key")

        assert value == "value2"

    @pytest.mark.asyncio
    async def test_pref_delete_removes_key(self, memory_store):
        """Test that pref_delete removes the key."""
        await memory_store.pref_set("to_delete", "value")

        deleted = await memory_store.pref_delete("to_delete")

        assert deleted is True
        assert await memory_store.pref_get("to_delete") is None

    @pytest.mark.asyncio
    async def test_pref_delete_returns_false_for_missing(self, memory_store):
        """Test that pref_delete returns False for missing key."""
        deleted = await memory_store.pref_delete("nonexistent")

        assert deleted is False

    @pytest.mark.asyncio
    async def test_pref_list_returns_all(self, memory_store):
        """Test that pref_list returns all preferences."""
        await memory_store.pref_set("key1", "value1")
        await memory_store.pref_set("key2", {"nested": True})

        prefs = await memory_store.pref_list()

        assert prefs == {"key1": "value1", "key2": {"nested": True}}


class TestEventLog:
    """Tests for event logging and querying."""

    @pytest.mark.asyncio
    async def test_record_event_returns_id(self, memory_store):
        """Test that record_event returns event ID."""
        event_id = await memory_store.record_event(
            event_type="orb_state_changed",
            source="pipeline",
            payload={"state": "listening"},
        )

        assert event_id == 1

    @pytest.mark.asyncio
    async def test_get_events_returns_newest_first(self, memory_store):
        """Test that events are returned newest first."""
        for i in range(3):
            await memory_store.record_event(
                event_type="test_event",
                source="test",
                payload={"index": i},
            )

        events = await memory_store.get_events()

        assert len(events) == 3
        assert events[0].payload["index"] == 2
        assert events[2].payload["index"] == 0

    @pytest.mark.asyncio
    async def test_get_events_filters_by_type(self, memory_store):
        """Test filtering events by type."""
        await memory_store.record_event("type_a", "test", {"data": "a"})
        await memory_store.record_event("type_b", "test", {"data": "b"})

        events_a = await memory_store.get_events(event_type="type_a")
        events_b = await memory_store.get_events(event_type="type_b")

        assert len(events_a) == 1
        assert events_a[0].type == "type_a"
        assert len(events_b) == 1
        assert events_b[0].type == "type_b"

    @pytest.mark.asyncio
    async def test_get_events_filters_by_source(self, memory_store):
        """Test filtering events by source."""
        await memory_store.record_event("event", "source_a", {"data": "a"})
        await memory_store.record_event("event", "source_b", {"data": "b"})

        events = await memory_store.get_events(source="source_a")

        assert len(events) == 1
        assert events[0].source == "source_a"

    @pytest.mark.asyncio
    async def test_get_events_respects_limit(self, memory_store):
        """Test that limit parameter is respected."""
        for i in range(10):
            await memory_store.record_event("event", "test", {"index": i})

        events = await memory_store.get_events(limit=3)

        assert len(events) == 3

    @pytest.mark.asyncio
    async def test_get_events_returns_event_type(self, memory_store):
        """Test that get_events returns Event objects."""
        await memory_store.record_event("test", "source", {"key": "value"})

        events = await memory_store.get_events()

        assert len(events) == 1
        assert isinstance(events[0], Event)
        assert events[0].payload == {"key": "value"}


class TestUtilityMethods:
    """Tests for utility methods."""

    @pytest.mark.asyncio
    async def test_get_session_ids(self, memory_store):
        """Test getting list of session IDs."""
        await memory_store.remember_turn("session-1", 0, "user", "Test 1")
        await memory_store.remember_turn("session-2", 0, "user", "Test 2")
        await memory_store.remember_turn("session-1", 1, "jarvis", "Response 1")

        sessions = await memory_store.get_session_ids()

        assert len(sessions) == 2
        assert "session-1" in sessions
        assert "session-2" in sessions

    @pytest.mark.asyncio
    async def test_delete_session(self, memory_store):
        """Test deleting a session."""
        await memory_store.remember_turn("to-delete", 0, "user", "Test")
        await memory_store.remember_turn("to-delete", 1, "jarvis", "Response")
        await memory_store.remember_turn("to-keep", 0, "user", "Keep this")

        deleted = await memory_store.delete_session("to-delete")

        assert deleted == 2

        remaining = await memory_store.get_recent_turns()
        assert len(remaining) == 1
        assert remaining[0].session_id == "to-keep"

    @pytest.mark.asyncio
    async def test_vacuum_runs_without_error(self, memory_store):
        """Test that vacuum runs without error."""
        await memory_store.remember_turn("test", 0, "user", "Test data")
        await memory_store.delete_session("test")

        await memory_store.vacuum()  # Should not raise
