"""Unit tests for ProactiveScheduler.

Tests cover:
- Scheduler initialization and lifecycle
- Event handling and interjection generation
- Cooldown enforcement
- Template formatting
- TTS and WebSocket delivery
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from brain.proactive import (
    INTERJECTION_TEMPLATES,
    Interjection,
    ProactiveScheduler,
)
from utils.events import Event, EventBus


@pytest.fixture
def event_bus():
    """Provide a fresh EventBus."""
    return EventBus()


@pytest.fixture
def proactive_config():
    """Provide default proactive configuration."""
    return {
        "enabled": True,
        "interjection_cooldown_seconds": 1,  # Short for testing
        "triggers": {
            "meeting_reminder": {"enabled": True, "voice": True},
            "vip_mail": {"enabled": True, "voice": True},
            "dirty_repo": {"enabled": True, "voice": False},
            "system_alert": {"enabled": True, "voice": True},
            "late_night_reminder": {"enabled": False, "voice": True},
        },
    }


@pytest.fixture
def tts_callback():
    """Provide a mock TTS callback."""
    return AsyncMock()


@pytest.fixture
def ws_broadcaster():
    """Provide a mock WebSocket broadcaster."""
    return AsyncMock()


@pytest_asyncio.fixture
async def scheduler(event_bus, proactive_config, tts_callback, ws_broadcaster):
    """Provide an initialized ProactiveScheduler."""
    sched = ProactiveScheduler(
        event_bus=event_bus,
        config=proactive_config,
        tts_callback=tts_callback,
        ws_broadcaster=ws_broadcaster,
        language="en",
    )
    await sched.start()
    yield sched
    await sched.stop()


class TestInterjection:
    """Tests for Interjection dataclass."""

    def test_interjection_has_id(self):
        """Test that interjection has auto-generated ID."""
        interjection = Interjection(message="Test")

        assert interjection.id
        assert len(interjection.id) == 8

    def test_interjection_defaults(self):
        """Test interjection default values."""
        interjection = Interjection()

        assert interjection.message == ""
        assert interjection.severity == "info"
        assert interjection.speak is True
        assert interjection.notification_payload == {}


class TestSchedulerLifecycle:
    """Tests for scheduler lifecycle management."""

    @pytest.mark.asyncio
    async def test_start_subscribes_to_events(
        self, event_bus, proactive_config, tts_callback, ws_broadcaster
    ):
        """Test that start subscribes to enabled event types."""
        scheduler = ProactiveScheduler(
            event_bus=event_bus,
            config=proactive_config,
            tts_callback=tts_callback,
            ws_broadcaster=ws_broadcaster,
        )

        await scheduler.start()

        # Should have handlers for enabled triggers
        assert event_bus.handler_count > 0
        assert len(event_bus.get_handlers("calendar_event_approaching")) == 1
        assert len(event_bus.get_handlers("vip_mail_received")) == 1

        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_stop_unsubscribes_from_events(
        self, event_bus, proactive_config, tts_callback, ws_broadcaster
    ):
        """Test that stop unsubscribes from events."""
        scheduler = ProactiveScheduler(
            event_bus=event_bus,
            config=proactive_config,
            tts_callback=tts_callback,
            ws_broadcaster=ws_broadcaster,
        )

        await scheduler.start()
        assert event_bus.handler_count > 0

        await scheduler.stop()
        # Handlers should be removed
        assert len(event_bus.get_handlers("calendar_event_approaching")) == 0

    @pytest.mark.asyncio
    async def test_disabled_scheduler_does_not_subscribe(
        self, event_bus, tts_callback, ws_broadcaster
    ):
        """Test that disabled scheduler does not subscribe."""
        config = {"enabled": False}
        scheduler = ProactiveScheduler(
            event_bus=event_bus,
            config=config,
            tts_callback=tts_callback,
            ws_broadcaster=ws_broadcaster,
        )

        await scheduler.start()

        assert scheduler.is_running is False
        assert event_bus.handler_count == 0


class TestCalendarEvents:
    """Tests for calendar event handling."""

    @pytest.mark.asyncio
    async def test_calendar_event_triggers_interjection(
        self, event_bus, scheduler, tts_callback, ws_broadcaster
    ):
        """Test that calendar event triggers interjection."""
        await event_bus.publish(
            Event(
                type="calendar_event_approaching",
                payload={"title": "Standup", "starts_in_minutes": 10},
            )
        )

        tts_callback.assert_called_once()
        call_args = tts_callback.call_args[0]
        assert "Standup" in call_args[0]
        assert "10 minutes" in call_args[0]

    @pytest.mark.asyncio
    async def test_calendar_event_5_min_uses_different_template(
        self, event_bus, scheduler, tts_callback
    ):
        """Test that 5-minute reminder uses different template."""
        await event_bus.publish(
            Event(
                type="calendar_event_approaching",
                payload={"title": "Meeting", "starts_in_minutes": 5},
            )
        )

        call_args = tts_callback.call_args[0]
        assert "5 minutes" in call_args[0]
        assert "wrapping up" in call_args[0].lower()


class TestVIPMail:
    """Tests for VIP mail handling."""

    @pytest.mark.asyncio
    async def test_vip_mail_triggers_interjection(
        self, event_bus, scheduler, tts_callback
    ):
        """Test that VIP mail triggers interjection."""
        await event_bus.publish(
            Event(
                type="vip_mail_received",
                payload={"sender": "Boss", "subject": "Important"},
            )
        )

        # Wait for cooldown from previous tests
        await asyncio.sleep(1.1)
        await event_bus.publish(
            Event(
                type="vip_mail_received",
                payload={"sender": "Boss", "subject": "Important"},
            )
        )

        assert tts_callback.called
        call_args = tts_callback.call_args[0]
        assert "Boss" in call_args[0]
        assert "Important" in call_args[0]


class TestSystemAlerts:
    """Tests for system alert handling."""

    @pytest.mark.asyncio
    async def test_cpu_alert_triggers_interjection(
        self, event_bus, scheduler, tts_callback
    ):
        """Test that CPU alert triggers interjection."""
        # Wait for cooldown
        await asyncio.sleep(1.1)

        await event_bus.publish(
            Event(
                type="system_threshold_exceeded",
                payload={"metric": "cpu", "value": 95, "threshold": 85},
            )
        )

        assert tts_callback.called
        call_args = tts_callback.call_args[0]
        assert "95" in call_args[0]

    @pytest.mark.asyncio
    async def test_urgent_gpu_alert_bypasses_cooldown(
        self, event_bus, proactive_config, tts_callback, ws_broadcaster
    ):
        """Test that urgent GPU alert bypasses cooldown."""
        scheduler = ProactiveScheduler(
            event_bus=event_bus,
            config=proactive_config,
            tts_callback=tts_callback,
            ws_broadcaster=ws_broadcaster,
        )
        await scheduler.start()

        # Trigger first alert
        await event_bus.publish(
            Event(
                type="system_threshold_exceeded",
                payload={"metric": "cpu", "value": 90, "threshold": 85},
            )
        )

        # Immediately trigger urgent GPU alert (should bypass cooldown)
        await event_bus.publish(
            Event(
                type="system_threshold_exceeded",
                payload={"metric": "gpu_temp", "value": 95, "threshold": 85},
            )
        )

        # Both should have been delivered
        assert tts_callback.call_count >= 2

        await scheduler.stop()


class TestCooldown:
    """Tests for cooldown enforcement."""

    @pytest.mark.asyncio
    async def test_cooldown_prevents_rapid_interjections(
        self, event_bus, proactive_config, tts_callback, ws_broadcaster
    ):
        """Test that cooldown prevents rapid interjections."""
        # Use longer cooldown
        proactive_config["interjection_cooldown_seconds"] = 5
        scheduler = ProactiveScheduler(
            event_bus=event_bus,
            config=proactive_config,
            tts_callback=tts_callback,
            ws_broadcaster=ws_broadcaster,
        )
        await scheduler.start()

        # First event should trigger
        await event_bus.publish(
            Event(
                type="calendar_event_approaching",
                payload={"title": "First", "starts_in_minutes": 10},
            )
        )

        # Second event immediately after should be skipped
        await event_bus.publish(
            Event(
                type="calendar_event_approaching",
                payload={"title": "Second", "starts_in_minutes": 10},
            )
        )

        # Only one call should have been made
        assert tts_callback.call_count == 1

        await scheduler.stop()


class TestTemplateFormatting:
    """Tests for interjection template formatting."""

    def test_all_templates_have_english(self):
        """Test that all templates have English version."""
        for key, templates in INTERJECTION_TEMPLATES.items():
            assert "en" in templates, f"Missing English template for {key}"

    def test_all_templates_have_german(self):
        """Test that all templates have German version."""
        for key, templates in INTERJECTION_TEMPLATES.items():
            assert "de" in templates, f"Missing German template for {key}"


class TestWebSocketBroadcast:
    """Tests for WebSocket notification broadcasting."""

    @pytest.mark.asyncio
    async def test_notification_broadcasted(
        self, event_bus, scheduler, ws_broadcaster
    ):
        """Test that notifications are broadcasted via WebSocket."""
        await event_bus.publish(
            Event(
                type="calendar_event_approaching",
                payload={"title": "Test", "starts_in_minutes": 10},
            )
        )

        ws_broadcaster.assert_called_once()
        call_args = ws_broadcaster.call_args[0]
        assert call_args[0] == "notification"
        assert "message" in call_args[1]
        assert "severity" in call_args[1]
