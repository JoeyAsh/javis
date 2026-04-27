"""Tests for brain.device_ledger — covers AC #6 (isolation), #9, #10.

Uses a tmp_path SQLite DB so no real filesystem side effects outside
the pytest tmp dir.  All tests are async; pytest-asyncio handles the
event loop.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helper: return a tmp-path DB path string for a given test.
# ---------------------------------------------------------------------------


def _db_path(tmp_path: Path, name: str = "test_ledger.db") -> str:
    return str(tmp_path / name)


# ---------------------------------------------------------------------------
# Schema + basic append / query
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ledger_init_creates_db_file(tmp_path: Path):
    """init() creates the SQLite file and parent directory."""
    from brain.device_ledger import DeviceLedger

    db_file = tmp_path / "sub" / "ledger.db"
    dl = DeviceLedger(db_path=str(db_file))
    await dl.init()
    assert db_file.exists()


@pytest.mark.asyncio
async def test_append_and_query_basic(tmp_path: Path):
    """append() then query() returns the inserted event."""
    from brain.device_ledger import DeviceLedger

    dl = DeviceLedger(db_path=_db_path(tmp_path))
    await dl.init()

    await dl.append("wake_word", "voice", {"model": "jarvis"}, correlation_id="cid-1")
    events = await dl.query(since="2000-01-01T00:00:00+00:00")
    assert len(events) == 1
    assert events[0].kind == "wake_word"
    assert events[0].source == "voice"
    assert events[0].payload["model"] == "jarvis"
    assert events[0].correlation_id == "cid-1"


@pytest.mark.asyncio
async def test_append_without_correlation_id_stores_null(tmp_path: Path):
    """correlation_id defaults to None and is stored as NULL."""
    from brain.device_ledger import DeviceLedger

    dl = DeviceLedger(db_path=_db_path(tmp_path))
    await dl.init()

    await dl.append("orb_state", "system", {"state": "idle"})
    events = await dl.query(since="2000-01-01T00:00:00+00:00")
    assert events[0].correlation_id is None


@pytest.mark.asyncio
async def test_append_all_valid_kinds(tmp_path: Path):
    """All schema-valid kind values can be appended without error."""
    from brain.device_ledger import DeviceLedger

    dl = DeviceLedger(db_path=_db_path(tmp_path))
    await dl.init()

    valid_kinds = [
        "tts_emitted", "mcp_call", "wake_word", "orb_state",
        "panel_open", "panel_close", "barge_in", "voice_turn_start",
        "voice_turn_end", "error",
    ]
    for kind in valid_kinds:
        await dl.append(kind, "voice", {})

    events = await dl.query(since="2000-01-01T00:00:00+00:00")
    assert len(events) == len(valid_kinds)


# ---------------------------------------------------------------------------
# AC #9 — append() does NOT raise on DB error.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_append_does_not_raise_on_operational_error(tmp_path: Path):
    """AC #9: append() swallows OperationalError; audio path is unaffected."""
    import aiosqlite
    from brain.device_ledger import DeviceLedger

    dl = DeviceLedger(db_path=_db_path(tmp_path, "failing.db"))
    await dl.init()

    # Patch aiosqlite.connect to raise OperationalError on every call.
    with patch("brain.device_ledger.aiosqlite.connect", side_effect=aiosqlite.OperationalError("DB locked")):
        # Must NOT raise.
        await dl.append("wake_word", "voice", {"test": True})


@pytest.mark.asyncio
async def test_append_does_not_raise_on_generic_exception(tmp_path: Path):
    """append() swallows any arbitrary Exception."""
    from brain.device_ledger import DeviceLedger

    dl = DeviceLedger(db_path=_db_path(tmp_path, "err.db"))
    await dl.init()

    with patch("brain.device_ledger.aiosqlite.connect", side_effect=RuntimeError("disk full")):
        await dl.append("mcp_call", "system", {})


# ---------------------------------------------------------------------------
# AC #10 — count_since returns dict[str, int] with all schema kinds.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_count_since_returns_all_kinds(tmp_path: Path):
    """AC #10: count_since() returns all schema-CHECK kinds as keys."""
    from brain.device_ledger import DeviceLedger

    dl = DeviceLedger(db_path=_db_path(tmp_path, "counts.db"))
    await dl.init()

    expected_kinds = {
        "tts_emitted", "mcp_call", "wake_word", "orb_state",
        "panel_open", "panel_close", "barge_in", "voice_turn_start",
        "voice_turn_end", "error",
    }
    counts = await dl.count_since(since="2000-01-01T00:00:00+00:00")
    assert set(counts.keys()) == expected_kinds


@pytest.mark.asyncio
async def test_count_since_returns_int_values(tmp_path: Path):
    """count_since() values are ints (AC #10 dict[str, int])."""
    from brain.device_ledger import DeviceLedger

    dl = DeviceLedger(db_path=_db_path(tmp_path, "int_vals.db"))
    await dl.init()

    counts = await dl.count_since(since="2000-01-01T00:00:00+00:00")
    for v in counts.values():
        assert isinstance(v, int)


@pytest.mark.asyncio
async def test_count_since_zero_on_empty_db(tmp_path: Path):
    """count_since() returns 0 for all kinds when the DB is empty."""
    from brain.device_ledger import DeviceLedger

    dl = DeviceLedger(db_path=_db_path(tmp_path, "zero.db"))
    await dl.init()

    counts = await dl.count_since(since="2000-01-01T00:00:00+00:00")
    assert all(v == 0 for v in counts.values())


@pytest.mark.asyncio
async def test_count_since_increments_correctly(tmp_path: Path):
    """count_since() reflects the correct per-kind tallies after appends."""
    from brain.device_ledger import DeviceLedger

    dl = DeviceLedger(db_path=_db_path(tmp_path, "incr.db"))
    await dl.init()

    await dl.append("tts_emitted", "voice", {"char_count": 50, "duration_ms": 1000})
    await dl.append("tts_emitted", "voice", {"char_count": 30, "duration_ms": 500})
    await dl.append("wake_word", "voice", {})

    counts = await dl.count_since(since="2000-01-01T00:00:00+00:00")
    assert counts["tts_emitted"] == 2
    assert counts["wake_word"] == 1
    assert counts["mcp_call"] == 0


@pytest.mark.asyncio
async def test_count_since_cutoff_filters_old_events(tmp_path: Path):
    """count_since() with a future cutoff returns 0 for all kinds."""
    from brain.device_ledger import DeviceLedger

    dl = DeviceLedger(db_path=_db_path(tmp_path, "future_cutoff.db"))
    await dl.init()

    await dl.append("tts_emitted", "voice", {"char_count": 10, "duration_ms": 100})

    # A far-future cutoff means nothing qualifies.
    counts = await dl.count_since(since="2099-01-01T00:00:00+00:00")
    assert all(v == 0 for v in counts.values())


# ---------------------------------------------------------------------------
# AC #7 (isolation) — tts_emitted row has correct char_count in payload.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tts_emitted_payload_char_count(tmp_path: Path):
    """tts_emitted rows store the correct char_count in payload_json."""
    from brain.device_ledger import DeviceLedger

    dl = DeviceLedger(db_path=_db_path(tmp_path, "tts_char.db"))
    await dl.init()

    text = "Hello Sir, welcome back."
    await dl.append(
        "tts_emitted",
        "voice",
        {"char_count": len(text), "duration_ms": 800, "voice_id": "fish-v1"},
    )
    events = await dl.query(since="2000-01-01T00:00:00+00:00")
    assert events[0].payload["char_count"] == len(text)
    assert events[0].payload["voice_id"] == "fish-v1"


# ---------------------------------------------------------------------------
# query() filter tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_query_filters_by_kind(tmp_path: Path):
    """query() with kinds filter only returns matching kinds."""
    from brain.device_ledger import DeviceLedger

    dl = DeviceLedger(db_path=_db_path(tmp_path, "kind_filter.db"))
    await dl.init()

    await dl.append("wake_word", "voice", {})
    await dl.append("tts_emitted", "voice", {"char_count": 10, "duration_ms": 100})
    await dl.append("mcp_call", "system", {"tool": "get_ha"})

    events = await dl.query(
        since="2000-01-01T00:00:00+00:00",
        kinds=["wake_word"],
    )
    assert len(events) == 1
    assert events[0].kind == "wake_word"


@pytest.mark.asyncio
async def test_query_limit(tmp_path: Path):
    """query() respects the limit parameter."""
    from brain.device_ledger import DeviceLedger

    dl = DeviceLedger(db_path=_db_path(tmp_path, "limit.db"))
    await dl.init()

    for i in range(20):
        await dl.append("orb_state", "system", {"state": f"s{i}"})

    events = await dl.query(since="2000-01-01T00:00:00+00:00", limit=5)
    assert len(events) <= 5


@pytest.mark.asyncio
async def test_query_returns_empty_list_on_db_error(tmp_path: Path):
    """query() returns [] instead of raising when the DB is inaccessible."""
    import aiosqlite
    from brain.device_ledger import DeviceLedger

    dl = DeviceLedger(db_path=_db_path(tmp_path, "query_err.db"))
    await dl.init()

    with patch("brain.device_ledger.aiosqlite.connect", side_effect=aiosqlite.OperationalError("locked")):
        result = await dl.query(since="2000-01-01T00:00:00+00:00")
    assert result == []


# ---------------------------------------------------------------------------
# recent() — basic check
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recent_returns_latest_events_descending(tmp_path: Path):
    """recent() returns events ordered by id ascending (chronological order)."""
    from brain.device_ledger import DeviceLedger

    dl = DeviceLedger(db_path=_db_path(tmp_path, "recent.db"))
    await dl.init()

    for kind in ["wake_word", "voice_turn_start", "tts_emitted"]:
        await dl.append(kind, "voice", {})

    events = await dl.recent(limit=10)
    assert len(events) == 3
    # recent() reverses back to chronological order (oldest first)
    assert events[0].kind == "wake_word"
    assert events[-1].kind == "tts_emitted"


@pytest.mark.asyncio
async def test_recent_returns_empty_list_on_db_error(tmp_path: Path):
    """recent() returns [] instead of raising when the DB is inaccessible."""
    import aiosqlite
    from brain.device_ledger import DeviceLedger

    dl = DeviceLedger(db_path=_db_path(tmp_path, "recent_err.db"))
    await dl.init()

    with patch("brain.device_ledger.aiosqlite.connect", side_effect=aiosqlite.OperationalError("locked")):
        result = await dl.recent()
    assert result == []


# ---------------------------------------------------------------------------
# Invalid kind — CHECK constraint triggers OperationalError → swallowed.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_append_invalid_kind_does_not_raise(tmp_path: Path):
    """Inserting an invalid kind triggers a CHECK constraint but append() swallows it."""
    from brain.device_ledger import DeviceLedger

    dl = DeviceLedger(db_path=_db_path(tmp_path, "invalid_kind.db"))
    await dl.init()

    # This will violate the SQL CHECK constraint (OperationalError).
    # append() must NOT propagate the exception.
    await dl.append("INVALID_KIND", "voice", {})
    # DB should still be queryable (existing rows unaffected).
    events = await dl.query(since="2000-01-01T00:00:00+00:00")
    # No rows were inserted (constraint violation rolled back).
    assert len(events) == 0
