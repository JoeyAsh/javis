"""MemoryStore: Async interface to JARVIS long-term memory database.

Provides persistent storage for:
- Conversation history (local transcript archive)
- User preferences (panel layout, voice settings)
- Event log (JARVIS-local events for HUD panels)

Uses SQLite with FTS5 for full-text search on conversations.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import aiosqlite

from brain.memory.schema import INIT_SQL
from utils.logger import get_logger

logger = get_logger("memory_store")


@dataclass
class ConversationTurn:
    """A single turn in a conversation."""

    id: int
    session_id: str
    turn_index: int
    role: str  # 'user' or 'jarvis'
    text: str
    timestamp: datetime
    intent_tag: str | None
    lang: str


@dataclass
class Event:
    """A logged event."""

    id: int
    type: str
    source: str
    payload: dict[str, Any]
    timestamp: datetime


class MemoryStore:
    """Async interface to JARVIS long-term memory database.

    This class provides persistent storage for UI/pipeline state only.
    Conversational context and facts are handled by OpenClaw.

    Attributes:
        db_path: Path to the SQLite database file.
    """

    def __init__(self, db_path: str = "data/jarvis.db") -> None:
        """Initialize memory store.

        Args:
            db_path: Path to SQLite database file. Directory will be
                created if it doesn't exist.
        """
        self._db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    @property
    def db_path(self) -> str:
        """Return the database path."""
        return self._db_path

    @property
    def is_connected(self) -> bool:
        """Check if database connection is open."""
        return self._conn is not None

    async def initialize(self) -> None:
        """Create database and tables if they don't exist.

        Creates the data directory if needed, opens the database connection,
        and executes the schema initialization SQL.

        Raises:
            aiosqlite.Error: If database initialization fails.
        """
        # Ensure data directory exists
        db_dir = Path(self._db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Initializing memory database at {self._db_path}")

        self._conn = await aiosqlite.connect(self._db_path)
        self._conn.row_factory = aiosqlite.Row

        # Enable foreign keys
        await self._conn.execute("PRAGMA foreign_keys = ON")

        # Execute schema initialization
        await self._conn.executescript(INIT_SQL)
        await self._conn.commit()

        logger.info("Memory database initialized successfully")

    async def close(self) -> None:
        """Close database connection.

        Safe to call multiple times or if not connected.
        """
        if self._conn:
            await self._conn.close()
            self._conn = None
            logger.debug("Memory database connection closed")

    async def _ensure_connected(self) -> None:
        """Ensure database is connected, initialize if not.

        Raises:
            RuntimeError: If connection cannot be established.
        """
        if self._conn is None:
            await self.initialize()

    # =========================================================================
    # Conversation methods
    # =========================================================================

    async def remember_turn(
        self,
        session_id: str,
        turn_index: int,
        role: str,
        text: str,
        intent_tag: str | None = None,
        lang: str = "en",
    ) -> int:
        """Store a conversation turn.

        Args:
            session_id: Unique session identifier.
            turn_index: Turn index within the session (0-based).
            role: Speaker role ('user' or 'jarvis').
            text: The spoken/written text.
            intent_tag: Optional intent classification tag.
            lang: Language code (default: 'en').

        Returns:
            The ID of the inserted turn.

        Raises:
            ValueError: If role is not 'user' or 'jarvis'.
            aiosqlite.Error: If database operation fails.
        """
        await self._ensure_connected()

        if role not in ("user", "jarvis"):
            raise ValueError(f"Invalid role: {role}. Must be 'user' or 'jarvis'.")

        async with self._conn.execute(
            """
            INSERT INTO conversations (session_id, turn_index, role, text, intent_tag, lang)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (session_id, turn_index, role, text, intent_tag, lang),
        ) as cursor:
            turn_id = cursor.lastrowid

        await self._conn.commit()
        logger.debug(f"Stored turn {turn_id}: {role} ({len(text)} chars)")
        return turn_id

    async def recall(
        self,
        query: str,
        limit: int = 10,
    ) -> list[ConversationTurn]:
        """Search conversation history via FTS5.

        Args:
            query: Search query (supports FTS5 syntax like "word1 AND word2").
            limit: Maximum number of results to return.

        Returns:
            List of matching conversation turns, ordered by relevance.
        """
        await self._ensure_connected()

        # FTS5 match query
        rows = await self._conn.execute_fetchall(
            """
            SELECT c.id, c.session_id, c.turn_index, c.role, c.text,
                   c.timestamp, c.intent_tag, c.lang
            FROM conversations c
            JOIN conversations_fts fts ON c.id = fts.rowid
            WHERE conversations_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (query, limit),
        )

        return [self._row_to_turn(row) for row in rows]

    async def get_recent_turns(
        self,
        session_id: str | None = None,
        limit: int = 20,
    ) -> list[ConversationTurn]:
        """Get recent conversation turns.

        Args:
            session_id: Filter to specific session (None = all sessions).
            limit: Maximum number of turns to return.

        Returns:
            List of recent turns, newest first.
        """
        await self._ensure_connected()

        if session_id:
            rows = await self._conn.execute_fetchall(
                """
                SELECT id, session_id, turn_index, role, text,
                       timestamp, intent_tag, lang
                FROM conversations
                WHERE session_id = ?
                ORDER BY timestamp DESC, id DESC
                LIMIT ?
                """,
                (session_id, limit),
            )
        else:
            rows = await self._conn.execute_fetchall(
                """
                SELECT id, session_id, turn_index, role, text,
                       timestamp, intent_tag, lang
                FROM conversations
                ORDER BY timestamp DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            )

        return [self._row_to_turn(row) for row in rows]

    def _row_to_turn(self, row: aiosqlite.Row) -> ConversationTurn:
        """Convert a database row to a ConversationTurn dataclass."""
        return ConversationTurn(
            id=row["id"],
            session_id=row["session_id"],
            turn_index=row["turn_index"],
            role=row["role"],
            text=row["text"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            intent_tag=row["intent_tag"],
            lang=row["lang"],
        )

    # =========================================================================
    # Preference methods
    # =========================================================================

    async def pref_get(self, key: str, default: Any = None) -> Any:
        """Get a preference value.

        Args:
            key: Preference key.
            default: Default value if key not found.

        Returns:
            Preference value (JSON-decoded) or default.
        """
        await self._ensure_connected()

        row = await self._conn.execute_fetchall(
            "SELECT value FROM preferences WHERE key = ?",
            (key,),
        )

        if not row:
            return default

        try:
            return json.loads(row[0]["value"])
        except json.JSONDecodeError:
            logger.warning(f"Failed to decode preference '{key}', returning raw value")
            return row[0]["value"]

    async def pref_set(self, key: str, value: Any) -> None:
        """Set a preference value.

        Args:
            key: Preference key.
            value: Value to store (will be JSON-encoded).
        """
        await self._ensure_connected()

        json_value = json.dumps(value)

        await self._conn.execute(
            """
            INSERT INTO preferences (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
            """,
            (key, json_value),
        )
        await self._conn.commit()
        logger.debug(f"Set preference '{key}'")

    async def pref_delete(self, key: str) -> bool:
        """Delete a preference.

        Args:
            key: Preference key to delete.

        Returns:
            True if deleted, False if key not found.
        """
        await self._ensure_connected()

        cursor = await self._conn.execute(
            "DELETE FROM preferences WHERE key = ?",
            (key,),
        )
        await self._conn.commit()

        deleted = cursor.rowcount > 0
        if deleted:
            logger.debug(f"Deleted preference '{key}'")
        return deleted

    async def pref_list(self) -> dict[str, Any]:
        """List all preferences.

        Returns:
            Dictionary of all preference key-value pairs.
        """
        await self._ensure_connected()

        rows = await self._conn.execute_fetchall(
            "SELECT key, value FROM preferences ORDER BY key"
        )

        result = {}
        for row in rows:
            try:
                result[row["key"]] = json.loads(row["value"])
            except json.JSONDecodeError:
                result[row["key"]] = row["value"]

        return result

    # =========================================================================
    # Event log methods
    # =========================================================================

    async def record_event(
        self,
        event_type: str,
        source: str,
        payload: dict[str, Any],
    ) -> int:
        """Record an event to the append-only log.

        Args:
            event_type: Event type (e.g., 'orb_state_changed', 'panel_toggled').
            source: Source module/agent name.
            payload: Event payload (will be JSON-encoded).

        Returns:
            Event ID.
        """
        await self._ensure_connected()

        payload_json = json.dumps(payload)

        async with self._conn.execute(
            """
            INSERT INTO events (type, source, payload_json)
            VALUES (?, ?, ?)
            """,
            (event_type, source, payload_json),
        ) as cursor:
            event_id = cursor.lastrowid

        await self._conn.commit()
        logger.debug(f"Recorded event {event_id}: {event_type} from {source}")
        return event_id

    async def get_events(
        self,
        event_type: str | None = None,
        source: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[Event]:
        """Query event log.

        Args:
            event_type: Filter by type (None = any).
            source: Filter by source (None = any).
            since: Filter to events after this time (None = any).
            limit: Maximum events to return.

        Returns:
            List of matching events, newest first.
        """
        await self._ensure_connected()

        # Build dynamic query
        conditions = []
        params: list[Any] = []

        if event_type:
            conditions.append("type = ?")
            params.append(event_type)

        if source:
            conditions.append("source = ?")
            params.append(source)

        if since:
            conditions.append("timestamp > ?")
            params.append(since.isoformat())

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        params.append(limit)

        rows = await self._conn.execute_fetchall(
            f"""
            SELECT id, type, source, payload_json, timestamp
            FROM events
            WHERE {where_clause}
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            params,
        )

        return [self._row_to_event(row) for row in rows]

    def _row_to_event(self, row: aiosqlite.Row) -> Event:
        """Convert a database row to an Event dataclass."""
        try:
            payload = json.loads(row["payload_json"])
        except json.JSONDecodeError:
            payload = {}

        return Event(
            id=row["id"],
            type=row["type"],
            source=row["source"],
            payload=payload,
            timestamp=datetime.fromisoformat(row["timestamp"]),
        )

    # =========================================================================
    # Utility methods
    # =========================================================================

    async def get_session_ids(self, limit: int = 50) -> list[str]:
        """Get list of unique session IDs, most recent first.

        Args:
            limit: Maximum number of session IDs to return.

        Returns:
            List of session ID strings.
        """
        await self._ensure_connected()

        rows = await self._conn.execute_fetchall(
            """
            SELECT session_id, MAX(timestamp) as last_ts
            FROM conversations
            GROUP BY session_id
            ORDER BY last_ts DESC
            LIMIT ?
            """,
            (limit,),
        )

        return [row["session_id"] for row in rows]

    async def delete_session(self, session_id: str) -> int:
        """Delete all turns for a session.

        Args:
            session_id: Session to delete.

        Returns:
            Number of turns deleted.
        """
        await self._ensure_connected()

        cursor = await self._conn.execute(
            "DELETE FROM conversations WHERE session_id = ?",
            (session_id,),
        )
        await self._conn.commit()

        deleted = cursor.rowcount
        logger.info(f"Deleted {deleted} turns from session {session_id}")
        return deleted

    async def vacuum(self) -> None:
        """Reclaim unused space in the database.

        Should be called periodically or after large deletions.
        """
        await self._ensure_connected()
        await self._conn.execute("VACUUM")
        logger.info("Database vacuumed")
