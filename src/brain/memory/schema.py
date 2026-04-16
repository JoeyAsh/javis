"""SQL schema definitions for JARVIS memory database.

Contains schema constants for SQLite + FTS5 tables:
- conversations: Local transcript archive for HUD
- preferences: Panel layout, voice settings, etc.
- events: JARVIS-local events for HUD panels
"""

# Schema version for migrations
SCHEMA_VERSION = 1

# Main schema SQL - executed on database initialization
SCHEMA_SQL = """
-- Conversation history (local archive for HUD)
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    turn_index INTEGER NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('user', 'jarvis')),
    text TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    intent_tag TEXT,
    lang TEXT DEFAULT 'en'
);

CREATE INDEX IF NOT EXISTS idx_conversations_session ON conversations(session_id);
CREATE INDEX IF NOT EXISTS idx_conversations_timestamp ON conversations(timestamp);

-- User preferences (panel layout, voice settings)
CREATE TABLE IF NOT EXISTS preferences (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Event log (JARVIS-local events for HUD panels)
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    source TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_events_type ON events(type);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

-- Insert initial version if not exists
INSERT OR IGNORE INTO schema_version (version) VALUES (1);
"""

# FTS5 virtual table for conversation search
FTS_SCHEMA_SQL = """
-- FTS5 for local transcript search
CREATE VIRTUAL TABLE IF NOT EXISTS conversations_fts USING fts5(
    text,
    content='conversations',
    content_rowid='id'
);
"""

# Triggers to keep FTS in sync with conversations table
FTS_TRIGGERS_SQL = """
-- Trigger: sync FTS on conversation insert
CREATE TRIGGER IF NOT EXISTS conversations_ai AFTER INSERT ON conversations BEGIN
    INSERT INTO conversations_fts(rowid, text) VALUES (new.id, new.text);
END;

-- Trigger: sync FTS on conversation delete
CREATE TRIGGER IF NOT EXISTS conversations_ad AFTER DELETE ON conversations BEGIN
    INSERT INTO conversations_fts(conversations_fts, rowid, text) VALUES('delete', old.id, old.text);
END;

-- Trigger: sync FTS on conversation update
CREATE TRIGGER IF NOT EXISTS conversations_au AFTER UPDATE ON conversations BEGIN
    INSERT INTO conversations_fts(conversations_fts, rowid, text) VALUES('delete', old.id, old.text);
    INSERT INTO conversations_fts(rowid, text) VALUES (new.id, new.text);
END;
"""

# Combined initialization SQL
INIT_SQL = SCHEMA_SQL + FTS_SCHEMA_SQL + FTS_TRIGGERS_SQL
