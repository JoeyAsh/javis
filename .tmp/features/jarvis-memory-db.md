# Feature Spec: JARVIS Long-Term Memory Database

## Status
Planned — awaiting implementation authorization

## Summary
Implement persistent long-term memory for JARVIS using SQLite + FTS5 + aiosqlite. This replaces the simple in-RAM `memory.py` conversation history with a full database supporting conversation history, learned user facts, preferences, detected routines, and a cross-domain event log.

## Goals
- Persistent storage of conversation history, user facts, preferences, routines, and events
- Fast text recall via FTS5 (full-text search)
- Power features like "remind me to X" recall, user-modeling, retrospective queries
- Async-first interface via `MemoryStore` class
- Daily backup with rotation (14 days)

## Non-Goals
- Vector search / embeddings (deferred to Phase B — note `sqlite-vec` as future path)
- External database server (SQLite single-file only)
- Real-time replication
- Multi-user isolation

---

## Technical Design

### Stack
- **SQLite** with FTS5 extension
- **aiosqlite** for async access
- Single-file database at `data/jarvis.db`

### Database Schema

```sql
-- Conversation history
CREATE TABLE conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    turn_index INTEGER NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('user', 'jarvis')),
    text TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    intent_tag TEXT,
    lang TEXT DEFAULT 'en'
);

CREATE INDEX idx_conversations_session ON conversations(session_id);
CREATE INDEX idx_conversations_timestamp ON conversations(timestamp);

-- RDF-ish fact tuples
CREATE TABLE facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject TEXT NOT NULL,
    predicate TEXT NOT NULL,
    object TEXT NOT NULL,
    confidence REAL DEFAULT 1.0,
    source TEXT,  -- 'user_stated', 'inferred', 'calendar', etc.
    first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_confirmed DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(subject, predicate, object)
);

CREATE INDEX idx_facts_subject ON facts(subject);
CREATE INDEX idx_facts_predicate ON facts(predicate);

-- User preferences
CREATE TABLE preferences (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Detected routines
CREATE TABLE routines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    pattern_json TEXT NOT NULL,  -- JSON describing the pattern
    schedule_cron TEXT,  -- optional cron expression
    last_triggered DATETIME,
    enabled INTEGER DEFAULT 1
);

-- Generic event log (append-only)
CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,  -- 'calendar_created', 'mail_sent', 'self_fix_applied', 'led_scene_changed', etc.
    source TEXT NOT NULL,  -- agent/module name
    payload_json TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_events_type ON events(type);
CREATE INDEX idx_events_source ON events(source);
CREATE INDEX idx_events_timestamp ON events(timestamp);

-- FTS5 virtual table for fast text recall
CREATE VIRTUAL TABLE conversations_fts USING fts5(
    text,
    content='conversations',
    content_rowid='id'
);

CREATE VIRTUAL TABLE facts_fts USING fts5(
    object,
    content='facts',
    content_rowid='id'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER conversations_ai AFTER INSERT ON conversations BEGIN
    INSERT INTO conversations_fts(rowid, text) VALUES (new.id, new.text);
END;

CREATE TRIGGER conversations_ad AFTER DELETE ON conversations BEGIN
    INSERT INTO conversations_fts(conversations_fts, rowid, text) VALUES('delete', old.id, old.text);
END;

CREATE TRIGGER facts_ai AFTER INSERT ON facts BEGIN
    INSERT INTO facts_fts(rowid, object) VALUES (new.id, new.object);
END;

CREATE TRIGGER facts_ad AFTER DELETE ON facts BEGIN
    INSERT INTO facts_fts(facts_fts, rowid, object) VALUES('delete', old.id, old.object);
END;
```

### File Structure
```
src/brain/memory/
    __init__.py
    store.py          # MemoryStore class
    schema.py         # SQL schema definitions
    backup.py         # Backup/rotation logic

data/
    jarvis.db         # Main database (gitignored)
    backups/          # Daily gzip snapshots (gitignored)
        jarvis-2026-04-15.db.gz
        jarvis-2026-04-14.db.gz
        ...
```

---

## MemoryStore Interface

```python
# src/brain/memory/store.py

from dataclasses import dataclass
from datetime import datetime
from typing import Any
import aiosqlite

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
class Fact:
    """An RDF-ish fact tuple."""
    id: int
    subject: str
    predicate: str
    object: str
    confidence: float
    source: str | None
    first_seen: datetime
    last_confirmed: datetime

@dataclass
class Event:
    """A logged event."""
    id: int
    type: str
    source: str
    payload: dict[str, Any]
    timestamp: datetime

class MemoryStore:
    """Async interface to JARVIS long-term memory database."""

    def __init__(self, db_path: str = "data/jarvis.db") -> None:
        """Initialize memory store.

        Args:
            db_path: Path to SQLite database file
        """
        self._db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        """Create database and tables if not exist."""
        ...

    async def close(self) -> None:
        """Close database connection."""
        ...

    # === Conversation methods ===

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
        
        Returns:
            Turn ID
        """
        ...

    async def recall(
        self,
        query: str,
        limit: int = 10,
    ) -> list[ConversationTurn]:
        """Search conversation history via FTS5.
        
        Args:
            query: Search query (supports FTS5 syntax)
            limit: Max results to return
            
        Returns:
            Matching conversation turns, most relevant first
        """
        ...

    async def get_recent_turns(
        self,
        session_id: str | None = None,
        limit: int = 20,
    ) -> list[ConversationTurn]:
        """Get recent conversation turns.
        
        Args:
            session_id: Filter to specific session (None = all sessions)
            limit: Max turns to return
            
        Returns:
            Recent turns, newest first
        """
        ...

    # === Fact methods ===

    async def fact_upsert(
        self,
        subject: str,
        predicate: str,
        object: str,
        confidence: float = 1.0,
        source: str | None = None,
    ) -> int:
        """Insert or update a fact.
        
        If fact exists (same subject+predicate+object), updates confidence and last_confirmed.
        
        Returns:
            Fact ID
        """
        ...

    async def fact_query(
        self,
        subject: str | None = None,
        predicate: str | None = None,
        min_confidence: float = 0.0,
    ) -> list[Fact]:
        """Query facts by subject/predicate.
        
        Args:
            subject: Filter by subject (None = any)
            predicate: Filter by predicate (None = any)
            min_confidence: Minimum confidence threshold
            
        Returns:
            Matching facts
        """
        ...

    async def fact_search(
        self,
        query: str,
        limit: int = 10,
    ) -> list[Fact]:
        """Search facts via FTS5 on object field.
        
        Args:
            query: Search query
            limit: Max results
            
        Returns:
            Matching facts
        """
        ...

    # === Preference methods ===

    async def pref_get(self, key: str, default: Any = None) -> Any:
        """Get a preference value.
        
        Args:
            key: Preference key
            default: Default if not found
            
        Returns:
            Preference value (JSON-decoded) or default
        """
        ...

    async def pref_set(self, key: str, value: Any) -> None:
        """Set a preference value.
        
        Args:
            key: Preference key
            value: Value (will be JSON-encoded)
        """
        ...

    async def pref_delete(self, key: str) -> bool:
        """Delete a preference.
        
        Returns:
            True if deleted, False if not found
        """
        ...

    # === Event log methods ===

    async def record_event(
        self,
        event_type: str,
        source: str,
        payload: dict[str, Any],
    ) -> int:
        """Record an event to the append-only log.
        
        Args:
            event_type: Event type (e.g., 'calendar_created', 'mail_sent')
            source: Source module/agent name
            payload: Event payload (will be JSON-encoded)
            
        Returns:
            Event ID
        """
        ...

    async def get_events(
        self,
        event_type: str | None = None,
        source: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[Event]:
        """Query event log.
        
        Args:
            event_type: Filter by type (None = any)
            source: Filter by source (None = any)
            since: Filter to events after this time (None = any)
            limit: Max events to return
            
        Returns:
            Matching events, newest first
        """
        ...
```

---

## Backup System

```python
# src/brain/memory/backup.py

import gzip
import shutil
from pathlib import Path
from datetime import datetime, timedelta

async def create_backup(db_path: str, backup_dir: str) -> str:
    """Create gzipped backup of database.

    Args:
        db_path: Path to source database
        backup_dir: Directory for backups

    Returns:
        Path to created backup file
    """
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    date_str = datetime.now().strftime("%Y-%m-%d")
    backup_path = backup_dir / f"jarvis-{date_str}.db.gz"
    
    with open(db_path, 'rb') as f_in:
        with gzip.open(backup_path, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
    
    return str(backup_path)

async def rotate_backups(backup_dir: str, keep_days: int = 14) -> int:
    """Delete backups older than keep_days.

    Args:
        backup_dir: Directory containing backups
        keep_days: Number of days to retain

    Returns:
        Number of deleted backups
    """
    backup_dir = Path(backup_dir)
    cutoff = datetime.now() - timedelta(days=keep_days)
    deleted = 0
    
    for backup_file in backup_dir.glob("jarvis-*.db.gz"):
        # Parse date from filename
        try:
            date_str = backup_file.stem.replace("jarvis-", "").replace(".db", "")
            file_date = datetime.strptime(date_str, "%Y-%m-%d")
            if file_date < cutoff:
                backup_file.unlink()
                deleted += 1
        except ValueError:
            continue
    
    return deleted
```

---

## Configuration

### config.yaml
```yaml
memory:
  enabled: true
  db_path: "data/jarvis.db"
  backup:
    enabled: true
    directory: "data/backups"
    keep_days: 14
    schedule: "0 3 * * *"  # 3 AM daily (cron format)
```

### .gitignore Update
Add to project `.gitignore`:
```
# JARVIS memory database
data/
data/backups/
```

---

## Migration from memory.py

The old `src/brain/memory.py` module is deprecated. Migration steps:

### Call Sites to Migrate

1. **`src/brain/orchestrator.py`**
   - Current: `from brain.memory import ConversationMemory`
   - New: `from brain.memory import MemoryStore`
   - Update: `self._memory = ConversationMemory()` → `self._memory = MemoryStore()`

2. **`src/brain/agents/chat_agent.py`**
   - Current: Uses `ConversationMemory` for history retrieval
   - New: Use `MemoryStore.get_recent_turns()` and `MemoryStore.remember_turn()`

3. **Any other imports of `ConversationMemory`**
   - Search codebase for `from brain.memory import`

### Migration Code Changes

```python
# Old usage
memory = ConversationMemory()
memory.add_turn("user", "Hello")
history = memory.get_history()

# New usage
memory = MemoryStore("data/jarvis.db")
await memory.initialize()
await memory.remember_turn(
    session_id="session-123",
    turn_index=0,
    role="user",
    text="Hello",
)
history = await memory.get_recent_turns(session_id="session-123")
```

### Deprecation Notice

Add to `src/brain/memory.py`:
```python
"""
DEPRECATED: This module is deprecated.
Use `from brain.memory import MemoryStore` instead.
This file will be removed in a future version.
"""
import warnings

warnings.warn(
    "brain.memory.ConversationMemory is deprecated. "
    "Use brain.memory.MemoryStore instead.",
    DeprecationWarning,
    stacklevel=2,
)
```

---

## Integration Points

### ProactiveScheduler / EventBus
Events from `jarvis-persona.md` flow into this database:
- Calendar events → `record_event('calendar_created', 'CalendarAgent', {...})`
- Mail sent → `record_event('mail_sent', 'EmailAgent', {...})`
- Self-fix applied → `record_event('self_fix_applied', 'SelfDebugAgent', {...})`
- LED scene changed → `record_event('led_scene_changed', 'SmartHomeAgent', {...})`

### ChatAgent
- Store each turn via `remember_turn()`
- Retrieve history for context via `get_recent_turns()`

### User Queries
- "What did I ask you yesterday about the calendar bug?" → `recall("calendar bug", ...)`
- "Remind me what my wife's favorite restaurant is" → `fact_search("favorite restaurant")`

### Claude Code Integration
- Self-fix events logged to `events` table
- Prerequisites: This spec must be implemented BEFORE `claude-code-integration.md`

---

## Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | Database created at `data/jarvis.db` on first run | Integration test |
| 2 | Conversation turns persist across JARVIS restarts | Integration test |
| 3 | FTS5 search returns relevant conversation turns | Unit test |
| 4 | Facts can be upserted and queried | Unit test |
| 5 | Preferences persist and retrieve correctly | Unit test |
| 6 | Events logged to append-only table | Unit test |
| 7 | Daily backup created at configured time | Integration test |
| 8 | Old backups rotated (14-day default) | Unit test |
| 9 | `data/` and `data/backups/` added to `.gitignore` | Code review |
| 10 | All call sites of old `memory.py` migrated | Code review |
| 11 | Old `memory.py` marked deprecated | Code review |
| 12 | MemoryStore exposes async methods only | Type check |

---

## Files Created

| File | Purpose |
|------|---------|
| `src/brain/memory/__init__.py` | Package init, exports MemoryStore |
| `src/brain/memory/store.py` | MemoryStore class |
| `src/brain/memory/schema.py` | SQL schema constants |
| `src/brain/memory/backup.py` | Backup/rotation logic |
| `data/.gitkeep` | Ensure data directory exists (empty file) |
| `tests/brain/memory/test_store.py` | Unit tests for MemoryStore |
| `tests/brain/memory/test_backup.py` | Unit tests for backup |

## Files Modified

| File | Change |
|------|--------|
| `.gitignore` | Add `data/`, `data/backups/` |
| `src/main.py` | Initialize MemoryStore, schedule backup task |
| `src/brain/orchestrator.py` | Use MemoryStore instead of ConversationMemory |
| `src/brain/agents/chat_agent.py` | Use MemoryStore for history |
| `config/config.yaml` | Add memory section |

## Files Deprecated

| File | Reason |
|------|--------|
| `src/brain/memory.py` | Replaced by `src/brain/memory/` package |

---

## Implementation Plan

### Batch 1 — Core database
1. `code` → Create `src/brain/memory/__init__.py`
2. `code` → Create `src/brain/memory/schema.py` with SQL schema constants
3. `code` → Create `src/brain/memory/store.py` with MemoryStore class
4. `test` → Create `tests/brain/memory/test_store.py`
5. `review` → Review batch 1

### Batch 2 — Backup system
6. `code` → Create `src/brain/memory/backup.py`
7. `code` → Update `src/main.py` with initialization and backup scheduling
8. `test` → Create `tests/brain/memory/test_backup.py`
9. `review` → Review batch 2

### Batch 3 — Migration
10. `code` → Update `.gitignore` with `data/` entries
11. `code` → Create `data/.gitkeep`
12. `code` → Update `src/brain/orchestrator.py` to use MemoryStore
13. `code` → Update `src/brain/agents/chat_agent.py` to use MemoryStore
14. `code` → Add deprecation warning to `src/brain/memory.py`
15. `code` → Add `memory` section to `config/config.yaml`
16. `test` → Integration tests for migration
17. `review` → Final review

---

## Dependencies

### pip packages
```
aiosqlite>=0.19.0
```

### Phase B Notes
Vector search is deferred to Phase B. Future implementation path:
- Use `sqlite-vec` extension for embedding-based similarity search
- Store embeddings alongside text in a separate table
- Integrate with sentence-transformers or similar for embedding generation

---

## Related Specs

- **Depends on this**: `claude-code-integration.md` (memory.py deprecation)
- **Integrates with**: `jarvis-persona.md` (event logging from ProactiveScheduler)
- **Cross-references**: All agent specs that log events

---

## Revision 3 — Scope Reduction for OpenClaw Adoption (2026-04-16)

### Decisions Applied
1. **OpenClaw as full backbone** — Session-level context delegated
2. **JARVIS MemoryStore scoped to UI/pipeline state only**

### Integration Assessment
**OpenClaw handles session context; JARVIS retains UI/pipeline state storage.**

### What OpenClaw Handles (DELEGATED)
| Feature | OpenClaw Capability |
|---------|---------------------|
| Conversational context | Per-session memory |
| Cross-session recall | OpenClaw memory system |
| Learned facts about user | OpenClaw workspace |
| Proactive triggers based on memory | OpenClaw standing orders |

### What JARVIS-Native Retains (REDUCED SCOPE)
MemoryStore scope is reduced to **UI/pipeline state only**:

| Table | Purpose | Status |
|-------|---------|--------|
| `conversations` | Local transcript archive for TranscriptPanel | KEEP |
| `preferences` | Panel layout, HUD prefs, voice settings | KEEP |
| `events` | JARVIS-local events for HUD panels | KEEP |
| `facts` | RDF-ish fact tuples | REMOVE (OpenClaw handles) |
| `routines` | Detected routines | REMOVE (OpenClaw handles) |

### Revised Schema
```sql
-- Conversation history (local archive for HUD)
CREATE TABLE conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    turn_index INTEGER NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('user', 'jarvis')),
    text TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    intent_tag TEXT,
    lang TEXT DEFAULT 'en'
);

CREATE INDEX idx_conversations_session ON conversations(session_id);
CREATE INDEX idx_conversations_timestamp ON conversations(timestamp);

-- User preferences (panel layout, voice settings)
CREATE TABLE preferences (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Event log (JARVIS-local events for HUD panels)
CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,  -- 'orb_state_changed', 'panel_toggled', 'self_fix_applied', etc.
    source TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_events_type ON events(type);
CREATE INDEX idx_events_timestamp ON events(timestamp);

-- FTS5 for local transcript search only
CREATE VIRTUAL TABLE conversations_fts USING fts5(
    text,
    content='conversations',
    content_rowid='id'
);
```

### REMOVED Tables
- ~~`facts`~~ — OpenClaw handles learned facts
- ~~`facts_fts`~~ — OpenClaw handles fact search
- ~~`routines`~~ — OpenClaw handles scheduling

### REMOVED Methods from MemoryStore
- ~~`fact_upsert()`~~ — OpenClaw handles
- ~~`fact_query()`~~ — OpenClaw handles
- ~~`fact_search()`~~ — OpenClaw handles

### KEPT Methods (UI/Pipeline Only)
```python
class MemoryStore:
    # Conversation archive (local HUD use)
    async def remember_turn(...) -> int
    async def recall(query: str, limit: int) -> list[ConversationTurn]
    async def get_recent_turns(...) -> list[ConversationTurn]
    
    # Preferences (panel layout, etc.)
    async def pref_get(key: str, default: Any) -> Any
    async def pref_set(key: str, value: Any) -> None
    async def pref_delete(key: str) -> bool
    
    # Event log (JARVIS-local events)
    async def record_event(event_type: str, source: str, payload: dict) -> int
    async def get_events(...) -> list[Event]
```

### Files Created — REDUCED
| File | Purpose | Status |
|------|---------|--------|
| `src/brain/memory/__init__.py` | Package init | KEEP |
| `src/brain/memory/store.py` | MemoryStore (reduced) | KEEP (simplified) |
| `src/brain/memory/schema.py` | SQL schema (reduced) | KEEP (simplified) |
| `src/brain/memory/backup.py` | Backup/rotation | KEEP |

### Implementation Reduction
**Original estimate:** 6-8 hours
**With OpenClaw:** 3-4 hours (UI state only)
**Reduction:** ~50%

### Prerequisites
- `openclaw-integration.md` — REQUIRED (handles conversational memory)

### Cross-References
- `jarvis-persona.md` — ProactiveScheduler events logged here
- `hud-panel-framework.md` — Panel preferences stored here
- `claude-code-integration.md` — Self-fix events logged here
