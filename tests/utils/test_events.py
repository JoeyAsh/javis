"""Unit tests for EventBus.

Tests cover:
- Event creation and attributes
- Handler subscription and unsubscription
- Event publishing and handler invocation
- Concurrent handler execution
- Error handling in handlers
"""

import asyncio

import pytest

from utils.events import Event, EventBus


class TestEvent:
    """Tests for Event dataclass."""

    def test_event_creation(self):
        """Test creating an event with payload."""
        event = Event(
            type="test_event",
            payload={"key": "value"},
        )

        assert event.type == "test_event"
        assert event.payload == {"key": "value"}
        assert event.timestamp > 0

    def test_event_default_payload(self):
        """Test that payload defaults to empty dict."""
        event = Event(type="test")

        assert event.payload == {}

    def test_event_timestamp_auto_generated(self):
        """Test that timestamp is auto-generated."""
        event1 = Event(type="test")
        event2 = Event(type="test")

        assert event1.timestamp > 0
        assert event2.timestamp >= event1.timestamp


class TestEventBusSubscription:
    """Tests for handler subscription."""

    def test_subscribe_adds_handler(self):
        """Test that subscribe adds a handler."""
        bus = EventBus()

        async def handler(event: Event):
            pass

        bus.subscribe("test", handler)

        assert bus.handler_count == 1
        assert handler in bus.get_handlers("test")

    def test_subscribe_multiple_handlers(self):
        """Test subscribing multiple handlers to same event."""
        bus = EventBus()

        async def handler1(event: Event):
            pass

        async def handler2(event: Event):
            pass

        bus.subscribe("test", handler1)
        bus.subscribe("test", handler2)

        assert bus.handler_count == 2
        assert len(bus.get_handlers("test")) == 2

    def test_subscribe_same_handler_twice_ignored(self):
        """Test that duplicate subscription is ignored."""
        bus = EventBus()

        async def handler(event: Event):
            pass

        bus.subscribe("test", handler)
        bus.subscribe("test", handler)

        assert bus.handler_count == 1

    def test_unsubscribe_removes_handler(self):
        """Test that unsubscribe removes a handler."""
        bus = EventBus()

        async def handler(event: Event):
            pass

        bus.subscribe("test", handler)
        bus.unsubscribe("test", handler)

        assert bus.handler_count == 0

    def test_unsubscribe_nonexistent_is_safe(self):
        """Test that unsubscribing nonexistent handler is safe."""
        bus = EventBus()

        async def handler(event: Event):
            pass

        bus.unsubscribe("test", handler)  # Should not raise

    def test_unsubscribe_all_clears_type(self):
        """Test that unsubscribe_all clears event type."""
        bus = EventBus()

        async def handler1(event: Event):
            pass

        async def handler2(event: Event):
            pass

        bus.subscribe("test", handler1)
        bus.subscribe("test", handler2)
        bus.subscribe("other", handler1)

        count = bus.unsubscribe_all("test")

        assert count == 2
        assert len(bus.get_handlers("test")) == 0
        assert len(bus.get_handlers("other")) == 1

    def test_unsubscribe_all_clears_everything(self):
        """Test that unsubscribe_all(None) clears everything."""
        bus = EventBus()

        async def handler(event: Event):
            pass

        bus.subscribe("test1", handler)
        bus.subscribe("test2", handler)

        count = bus.unsubscribe_all()

        assert count == 2
        assert bus.handler_count == 0


class TestEventPublishing:
    """Tests for event publishing."""

    @pytest.mark.asyncio
    async def test_publish_calls_handler(self):
        """Test that publish invokes subscribed handler."""
        bus = EventBus()
        received = []

        async def handler(event: Event):
            received.append(event)

        bus.subscribe("test", handler)
        await bus.publish(Event(type="test", payload={"data": 1}))

        assert len(received) == 1
        assert received[0].payload == {"data": 1}

    @pytest.mark.asyncio
    async def test_publish_calls_multiple_handlers(self):
        """Test that publish invokes all handlers."""
        bus = EventBus()
        results = []

        async def handler1(event: Event):
            results.append("handler1")

        async def handler2(event: Event):
            results.append("handler2")

        bus.subscribe("test", handler1)
        bus.subscribe("test", handler2)
        await bus.publish(Event(type="test"))

        assert len(results) == 2
        assert "handler1" in results
        assert "handler2" in results

    @pytest.mark.asyncio
    async def test_publish_with_no_handlers(self):
        """Test that publish with no handlers does not raise."""
        bus = EventBus()

        await bus.publish(Event(type="unhandled"))  # Should not raise

    @pytest.mark.asyncio
    async def test_publish_only_invokes_matching_handlers(self):
        """Test that only handlers for event type are invoked."""
        bus = EventBus()
        received_types = []

        async def handler_a(event: Event):
            received_types.append("a")

        async def handler_b(event: Event):
            received_types.append("b")

        bus.subscribe("type_a", handler_a)
        bus.subscribe("type_b", handler_b)

        await bus.publish(Event(type="type_a"))

        assert received_types == ["a"]

    @pytest.mark.asyncio
    async def test_handler_error_does_not_stop_others(self):
        """Test that error in one handler doesn't stop others."""
        bus = EventBus()
        results = []

        async def error_handler(event: Event):
            raise ValueError("Handler error")

        async def good_handler(event: Event):
            results.append("success")

        bus.subscribe("test", error_handler)
        bus.subscribe("test", good_handler)

        await bus.publish(Event(type="test"))

        assert "success" in results


class TestEventBusQueries:
    """Tests for EventBus query methods."""

    def test_get_handlers_returns_copy(self):
        """Test that get_handlers returns a copy, not the original."""
        bus = EventBus()

        async def handler(event: Event):
            pass

        bus.subscribe("test", handler)
        handlers = bus.get_handlers("test")
        handlers.clear()  # Modify the copy

        assert len(bus.get_handlers("test")) == 1  # Original unchanged

    def test_get_handlers_empty_for_unknown_type(self):
        """Test that get_handlers returns empty list for unknown type."""
        bus = EventBus()

        handlers = bus.get_handlers("unknown")

        assert handlers == []

    def test_get_event_types(self):
        """Test listing registered event types."""
        bus = EventBus()

        async def handler(event: Event):
            pass

        bus.subscribe("type_a", handler)
        bus.subscribe("type_b", handler)

        types = bus.get_event_types()

        assert set(types) == {"type_a", "type_b"}
