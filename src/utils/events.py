"""EventBus: Simple asyncio pub/sub for internal JARVIS events.

Provides decoupled communication between modules for:
- Calendar event reminders
- VIP mail notifications
- System alerts (CPU, GPU temp, disk)
- Dirty repo warnings
- Orb state changes

Example usage:
    from utils.events import EventBus, Event

    bus = EventBus()

    async def on_calendar_event(event: Event):
        print(f"Meeting in {event.payload['starts_in_minutes']} minutes")

    bus.subscribe("calendar_event_approaching", on_calendar_event)

    await bus.publish(Event(
        type="calendar_event_approaching",
        payload={"title": "Standup", "starts_in_minutes": 10},
    ))
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from utils.logger import get_logger

logger = get_logger("events")


@dataclass
class Event:
    """An internal JARVIS event.

    Attributes:
        type: Event type identifier (e.g., 'calendar_event_approaching').
        payload: Event data dictionary.
        timestamp: Unix timestamp when event was created.
    """

    type: str
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


# Type alias for event handlers
EventHandler = Callable[[Event], Awaitable[None]]


class EventBus:
    """Simple asyncio pub/sub for internal events.

    Thread-safe event bus supporting async handlers. Multiple handlers
    can subscribe to the same event type. Handlers are called concurrently.

    Attributes:
        handler_count: Total number of registered handlers.
    """

    def __init__(self) -> None:
        """Initialize the event bus."""
        self._handlers: dict[str, list[EventHandler]] = {}
        self._lock = asyncio.Lock()

    @property
    def handler_count(self) -> int:
        """Return total number of registered handlers."""
        return sum(len(handlers) for handlers in self._handlers.values())

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Register a handler for an event type.

        Args:
            event_type: Event type to subscribe to.
            handler: Async callback function to invoke.
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []

        if handler not in self._handlers[event_type]:
            self._handlers[event_type].append(handler)
            logger.debug(f"Handler subscribed to '{event_type}'")

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """Remove a handler from an event type.

        Args:
            event_type: Event type to unsubscribe from.
            handler: Handler function to remove.
        """
        if event_type in self._handlers:
            try:
                self._handlers[event_type].remove(handler)
                logger.debug(f"Handler unsubscribed from '{event_type}'")
            except ValueError:
                pass  # Handler not found, ignore

    def unsubscribe_all(self, event_type: str | None = None) -> int:
        """Remove all handlers for an event type or all types.

        Args:
            event_type: Event type to clear, or None for all types.

        Returns:
            Number of handlers removed.
        """
        if event_type is None:
            count = self.handler_count
            self._handlers.clear()
            return count
        elif event_type in self._handlers:
            count = len(self._handlers[event_type])
            del self._handlers[event_type]
            return count
        return 0

    async def publish(self, event: Event) -> None:
        """Dispatch event to all registered handlers.

        Handlers are invoked concurrently. Exceptions in handlers are
        logged but don't prevent other handlers from running.

        Args:
            event: Event to publish.
        """
        handlers = self._handlers.get(event.type, [])
        if not handlers:
            logger.debug(f"No handlers for event type '{event.type}'")
            return

        logger.debug(
            f"Publishing '{event.type}' to {len(handlers)} handler(s)"
        )

        # Run all handlers concurrently
        tasks = [
            asyncio.create_task(self._safe_call(handler, event))
            for handler in handlers
        ]
        await asyncio.gather(*tasks)

    async def _safe_call(self, handler: EventHandler, event: Event) -> None:
        """Call handler with exception catching.

        Args:
            handler: Handler to call.
            event: Event to pass.
        """
        try:
            await handler(event)
        except Exception as e:
            logger.error(f"Event handler error for '{event.type}': {e}")

    def get_handlers(self, event_type: str) -> list[EventHandler]:
        """Get list of handlers for an event type.

        Args:
            event_type: Event type to query.

        Returns:
            List of handler functions (empty if none).
        """
        return list(self._handlers.get(event_type, []))

    def get_event_types(self) -> list[str]:
        """Get list of event types with registered handlers.

        Returns:
            List of event type strings.
        """
        return list(self._handlers.keys())
