"""Device-Event Ledger for JARVIS.

Append-only SQLite store tracking device-local events: TTS emissions,
MCP calls, wake-word detections, orb state transitions, panel open/close,
barge-in, and voice-turn boundaries.

Backed by aiosqlite with WAL mode for write-burst tolerance (RPi 5 SD-card).
All public methods are async; ``append()`` is explicitly non-raising so it
never blocks the voice pipeline on DB failure.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiosqlite

from utils.config_loader import get_config
from utils.logger import get_logger

logger = get_logger("device_ledger")

# Valid kind values — kept in sync with the SQL CHECK constraint.
_VALID_KINDS: frozenset[str] = frozenset(
    {
        "tts_emitted",
        "mcp_call",
        "wake_word",
        "orb_state",
        "panel_open",
        "panel_close",
        "barge_in",
        "voice_turn_start",
        "voice_turn_end",
        "error",
    }
)

# Valid source values — kept in sync with the SQL CHECK constraint.
_VALID_SOURCES: frozenset[str] = frozenset({"voice", "hud", "scheduler", "system"})

_DDL = """\
CREATE TABLE IF NOT EXISTS device_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  correlation_id TEXT,
  kind TEXT NOT NULL CHECK(kind IN
    ('tts_emitted','mcp_call','wake_word','orb_state','panel_open',
     'panel_close','barge_in','voice_turn_start','voice_turn_end','error')),
  source TEXT NOT NULL CHECK(source IN ('voice','hud','scheduler','system')),
  ts TEXT NOT NULL,
  payload_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_de_ts ON device_events(ts);
CREATE INDEX IF NOT EXISTS idx_de_kind ON device_events(kind);
CREATE INDEX IF NOT EXISTS idx_de_corr ON device_events(correlation_id);
"""


@dataclass
class DeviceEvent:
    """A single recorded device event."""

    id: int
    correlation_id: str | None
    kind: str
    source: str
    ts: str
    payload: dict[str, Any]


class DeviceLedger:
    """Append-only SQLite ledger for JARVIS device events.

    Lifecycle: call ``await ledger.init()`` once before use.

    Instantiate with an optional ``db_path`` override; defaults to
    ``state/device_ledger.db`` from config.
    """

    def __init__(self, db_path: str | None = None) -> None:
        """Initialise the ledger with the given DB path.

        Args:
            db_path: Filesystem path to the SQLite file.  When ``None``
                the path is read from ``device_ledger.db_path`` in config;
                defaults to ``state/device_ledger.db``.
        """
        if db_path is None:
            cfg = get_config()
            ledger_cfg = cfg.get_section("device_ledger") or {}
            db_path = str(ledger_cfg.get("db_path", "state/device_ledger.db"))
        self._db_path = Path(db_path)
        self._wal_mode: bool = True  # set during init()

    async def init(self) -> None:
        """Create the database directory, run DDL, and enable WAL mode.

        Must be awaited exactly once before any other method.
        """
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        # Read wal_mode from config.
        try:
            cfg = get_config()
            ledger_cfg = cfg.get_section("device_ledger") or {}
            self._wal_mode = bool(ledger_cfg.get("wal_mode", True))
        except Exception:
            self._wal_mode = True

        async with aiosqlite.connect(str(self._db_path)) as db:
            if self._wal_mode:
                await db.execute("PRAGMA journal_mode=WAL")
            await db.executescript(_DDL)
            await db.commit()

        logger.info(f"DeviceLedger initialised at {self._db_path} (WAL={self._wal_mode})")

    async def append(
        self,
        kind: str,
        source: str,
        payload: dict[str, Any],
        correlation_id: str | None = None,
    ) -> None:
        """Append an event row.  Never raises — all errors are logged as WARN.

        Args:
            kind: Event kind (must be one of the schema CHECK values).
            source: Event source (``voice``, ``hud``, ``scheduler``, ``system``).
            payload: Arbitrary dict; serialised to JSON for storage.
            correlation_id: Optional per-turn UUID grouping key.
        """
        try:
            ts = _iso_now()
            payload_json = json.dumps(payload, default=str)
            async with aiosqlite.connect(str(self._db_path)) as db:
                if self._wal_mode:
                    await db.execute("PRAGMA journal_mode=WAL")
                await db.execute(
                    "INSERT INTO device_events "
                    "(correlation_id, kind, source, ts, payload_json) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (correlation_id, kind, source, ts, payload_json),
                )
                await db.commit()
        except Exception as exc:
            logger.warning(
                f"DeviceLedger.append failed (kind={kind!r}, source={source!r}): {exc}"
            )

    async def query(
        self,
        since: str,
        until: str | None = None,
        kinds: list[str] | None = None,
        limit: int = 50,
    ) -> list[DeviceEvent]:
        """Query events with optional filters.

        Args:
            since: ISO-8601 timestamp lower bound (inclusive).
            until: ISO-8601 timestamp upper bound (inclusive).  ``None``
                means no upper bound.
            kinds: Filter to these event kinds.  ``None`` means all kinds.
            limit: Maximum rows returned (default 50).

        Returns:
            List of :class:`DeviceEvent` ordered by ``ts`` ascending.
        """
        try:
            conditions = ["ts >= ?"]
            params: list[Any] = [since]

            if until is not None:
                conditions.append("ts <= ?")
                params.append(until)

            if kinds:
                placeholders = ",".join("?" for _ in kinds)
                conditions.append(f"kind IN ({placeholders})")
                params.extend(kinds)

            where = " AND ".join(conditions)
            params.append(limit)

            sql = (
                f"SELECT id, correlation_id, kind, source, ts, payload_json "
                f"FROM device_events WHERE {where} ORDER BY ts ASC LIMIT ?"
            )

            async with aiosqlite.connect(str(self._db_path)) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(sql, params) as cursor:
                    rows = await cursor.fetchall()

            return [_row_to_event(row) for row in rows]

        except Exception as exc:
            logger.warning(f"DeviceLedger.query failed: {exc}")
            return []

    async def count_since(self, since: str) -> dict[str, int]:
        """Return per-kind event counts from ``since`` to now.

        Args:
            since: ISO-8601 timestamp lower bound (inclusive).

        Returns:
            Dict mapping every schema-valid kind to its count (0 when absent).
        """
        result: dict[str, int] = {kind: 0 for kind in _VALID_KINDS}
        try:
            async with aiosqlite.connect(str(self._db_path)) as db:
                async with db.execute(
                    "SELECT kind, COUNT(*) FROM device_events WHERE ts >= ? GROUP BY kind",
                    (since,),
                ) as cursor:
                    rows = await cursor.fetchall()
            for row in rows:
                kind, count = row[0], row[1]
                result[kind] = int(count)
        except Exception as exc:
            logger.warning(f"DeviceLedger.count_since failed: {exc}")
        return result

    async def recent(self, limit: int = 10) -> list[DeviceEvent]:
        """Return the most recent events.

        Args:
            limit: Maximum rows returned.

        Returns:
            List of :class:`DeviceEvent` ordered by ``id`` descending.
        """
        try:
            async with aiosqlite.connect(str(self._db_path)) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    "SELECT id, correlation_id, kind, source, ts, payload_json "
                    "FROM device_events ORDER BY id DESC LIMIT ?",
                    (limit,),
                ) as cursor:
                    rows = await cursor.fetchall()
            # Return in chronological order (oldest first).
            return [_row_to_event(row) for row in reversed(list(rows))]
        except Exception as exc:
            logger.warning(f"DeviceLedger.recent failed: {exc}")
            return []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_event(row: aiosqlite.Row) -> DeviceEvent:
    """Convert an aiosqlite Row to a DeviceEvent dataclass."""
    try:
        payload = json.loads(row["payload_json"])
    except Exception:
        payload = {}
    return DeviceEvent(
        id=row["id"],
        correlation_id=row["correlation_id"],
        kind=row["kind"],
        source=row["source"],
        ts=row["ts"],
        payload=payload,
    )


def _iso_now() -> str:
    """Return current UTC time as ISO-8601 string."""
    import datetime

    return datetime.datetime.now(datetime.timezone.utc).isoformat()
