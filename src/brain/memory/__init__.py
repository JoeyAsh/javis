"""JARVIS long-term memory database package.

Provides persistent storage for UI/pipeline state:
- Conversation history (local transcript archive)
- User preferences (panel layout, voice settings)
- Event log (JARVIS-local events for HUD panels)

Example usage:
    from brain.memory import MemoryStore

    store = MemoryStore("data/jarvis.db")
    await store.initialize()

    # Store a conversation turn
    await store.remember_turn(
        session_id="session-123",
        turn_index=0,
        role="user",
        text="What's the weather like?",
        lang="en",
    )

    # Search conversations
    results = await store.recall("weather")

    # Preferences
    await store.pref_set("panel_layout", {"left": ["transcript"]})
    layout = await store.pref_get("panel_layout")

    # Events
    await store.record_event("orb_state_changed", "pipeline", {"state": "listening"})

    await store.close()
"""

from brain.memory.backup import (
    create_backup,
    list_backups,
    restore_backup,
    rotate_backups,
)
from brain.memory.store import ConversationTurn, Event, MemoryStore

__all__ = [
    "MemoryStore",
    "ConversationTurn",
    "Event",
    "create_backup",
    "rotate_backups",
    "restore_backup",
    "list_backups",
]
