"""ProactiveScheduler: Event-driven interjections for JARVIS.

Listens to the EventBus and generates contextual interjections like:
- Meeting reminders (10 min, 5 min before)
- VIP mail notifications
- Dirty repo warnings
- System alerts (CPU, GPU temp, disk)

The scheduler respects a cooldown period to avoid being annoying.
Interjections can be spoken via TTS and/or shown in notifications.

Example usage:
    from brain.proactive import ProactiveScheduler, Interjection
    from utils.events import EventBus

    bus = EventBus()
    scheduler = ProactiveScheduler(
        event_bus=bus,
        config=config["proactive"],
        tts_callback=tts_speak,
        ws_broadcaster=broadcast_notification,
    )
    await scheduler.start()

    # Events published to bus will trigger interjections
    await bus.publish(Event(
        type="calendar_event_approaching",
        payload={"title": "Standup", "starts_in_minutes": 10},
    ))
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from utils.events import Event, EventBus
from utils.logger import get_logger

logger = get_logger("proactive")


@dataclass
class Interjection:
    """A proactive message from JARVIS.

    Attributes:
        id: Unique identifier.
        message: Spoken text.
        severity: Urgency level ("info", "warning", "urgent").
        speak: Whether to synthesize TTS.
        notification_payload: Data for NotificationsPanel.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    message: str = ""
    severity: str = "info"  # "info" | "warning" | "urgent"
    speak: bool = True
    notification_payload: dict[str, Any] = field(default_factory=dict)


# Interjection message templates
INTERJECTION_TEMPLATES = {
    "meeting_reminder_10": {
        "en": "Sir, your meeting '{title}' begins in 10 minutes.",
        "de": "Sir, Ihr Termin '{title}' beginnt in 10 Minuten.",
    },
    "meeting_reminder_5": {
        "en": "Sir, '{title}' starts in 5 minutes. I suggest wrapping up your current task.",
        "de": "Sir, '{title}' beginnt in 5 Minuten. Ich empfehle, die aktuelle Aufgabe abzuschließen.",
    },
    "vip_mail": {
        "en": "Sir, you've received an email from {sender} regarding '{subject}'. It may warrant your attention.",
        "de": "Sir, Sie haben eine E-Mail von {sender} erhalten, betreffend '{subject}'. Sie könnte Ihre Aufmerksamkeit verdienen.",
    },
    "dirty_repo": {
        "en": "Sir, you have uncommitted changes on branch '{branch}' in {repo}. It's been {minutes} minutes since your last activity there.",
        "de": "Sir, Sie haben nicht commitete Änderungen auf Branch '{branch}' in {repo}. Es sind {minutes} Minuten seit Ihrer letzten Aktivität dort vergangen.",
    },
    "system_cpu": {
        "en": "Sir, CPU utilization has exceeded {threshold}%. Current load is {value}%.",
        "de": "Sir, die CPU-Auslastung hat {threshold}% überschritten. Aktuelle Last: {value}%.",
    },
    "system_gpu_temp": {
        "en": "Sir, GPU temperature has reached {value} degrees Celsius. I recommend monitoring the situation.",
        "de": "Sir, die GPU-Temperatur hat {value} Grad Celsius erreicht. Ich empfehle, die Situation zu beobachten.",
    },
    "system_disk": {
        "en": "Sir, disk usage has exceeded {threshold}%. Current usage is {value}%.",
        "de": "Sir, die Festplattennutzung hat {threshold}% überschritten. Aktuelle Nutzung: {value}%.",
    },
    "late_night": {
        "en": "Sir, it's getting late. Perhaps a reasonable bedtime?",
        "de": "Sir, es wird spät. Vielleicht eine vernünftige Schlafenszeit?",
    },
}


class ProactiveScheduler:
    """Listens to EventBus and generates contextual interjections.

    The scheduler subscribes to specific event types and generates
    appropriate interjections based on configuration and cooldown logic.

    Attributes:
        event_bus: The event bus to subscribe to.
        is_running: Whether the scheduler is active.
    """

    def __init__(
        self,
        event_bus: EventBus,
        config: dict[str, Any],
        tts_callback: Callable[[str, str], Awaitable[None]],
        ws_broadcaster: Callable[[str, dict[str, Any]], Awaitable[None]],
        language: str = "en",
    ) -> None:
        """Initialize the proactive scheduler.

        Args:
            event_bus: EventBus instance to subscribe to.
            config: Proactive configuration section containing trigger settings.
            tts_callback: Async function (text, language) -> speak via TTS.
            ws_broadcaster: Async function (type, payload) -> broadcast to frontend.
            language: Default language for interjections.
        """
        self._event_bus = event_bus
        self._config = config
        self._tts_callback = tts_callback
        self._ws_broadcaster = ws_broadcaster
        self._language = language
        self._is_running = False
        self._last_interjection_time: float = 0.0
        self._cooldown_seconds = config.get("interjection_cooldown_seconds", 300)
        # Separate cooldown for calendar reminders — shorter than the global gate
        # so that 10/5/1-minute threshold reminders are not blocked by a VIP mail
        # interjection, while still preventing two calendar events from firing in
        # the same second.
        self._last_calendar_interjection_time: float = 0.0
        self._calendar_reminder_cooldown_seconds: float = 30.0

    @property
    def event_bus(self) -> EventBus:
        """Return the event bus."""
        return self._event_bus

    @property
    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self._is_running

    async def start(self) -> None:
        """Subscribe to relevant events and start the scheduler.

        Safe to call multiple times - will not re-subscribe if already running.
        """
        if self._is_running:
            logger.debug("ProactiveScheduler already running")
            return

        if not self._config.get("enabled", True):
            logger.info("ProactiveScheduler disabled in config")
            return

        logger.info("Starting ProactiveScheduler")

        # Subscribe to event types based on enabled triggers
        triggers = self._config.get("triggers", {})

        if triggers.get("meeting_reminder", {}).get("enabled", True):
            self._event_bus.subscribe(
                "calendar_event_approaching",
                self._handle_calendar_event,
            )

        if triggers.get("vip_mail", {}).get("enabled", True):
            self._event_bus.subscribe(
                "vip_mail_received",
                self._handle_vip_mail,
            )

        if triggers.get("dirty_repo", {}).get("enabled", True):
            self._event_bus.subscribe(
                "repo_dirty_idle",
                self._handle_repo_dirty,
            )

        if triggers.get("system_alert", {}).get("enabled", True):
            self._event_bus.subscribe(
                "system_threshold_exceeded",
                self._handle_system_alert,
            )

        if triggers.get("late_night_reminder", {}).get("enabled", False):
            self._event_bus.subscribe(
                "late_night_detected",
                self._handle_late_night,
            )

        self._is_running = True
        logger.info("ProactiveScheduler started with subscriptions")

    async def stop(self) -> None:
        """Unsubscribe from events and stop the scheduler."""
        if not self._is_running:
            return

        logger.info("Stopping ProactiveScheduler")

        # Unsubscribe from all events
        self._event_bus.unsubscribe(
            "calendar_event_approaching",
            self._handle_calendar_event,
        )
        self._event_bus.unsubscribe(
            "vip_mail_received",
            self._handle_vip_mail,
        )
        self._event_bus.unsubscribe(
            "repo_dirty_idle",
            self._handle_repo_dirty,
        )
        self._event_bus.unsubscribe(
            "system_threshold_exceeded",
            self._handle_system_alert,
        )
        self._event_bus.unsubscribe(
            "late_night_detected",
            self._handle_late_night,
        )

        self._is_running = False
        logger.info("ProactiveScheduler stopped")

    def _can_interject(self, severity: str = "info", event_type: str = "") -> bool:
        """Check if an interjection is allowed based on cooldown.

        Args:
            severity: Interjection severity. "urgent" bypasses cooldown.
            event_type: Optional EventBus event type name. Calendar reminder
                events (starting with "calendar_") bypass the global cooldown
                so that 10/5/1-minute reminders always fire.

        Returns:
            True if interjection is allowed.
        """
        # Urgent interjections bypass cooldown
        if severity == "urgent":
            return True

        # Calendar reminder triggers use their own short cooldown (30 s) so that
        # they are not blocked by a prior VIP-mail or system-alert interjection
        # (the global 5-minute gate), while still preventing two calendar events
        # from firing within the same polling cycle.
        if event_type.startswith("calendar_"):
            now = time.time()
            elapsed = now - self._last_calendar_interjection_time
            return elapsed >= self._calendar_reminder_cooldown_seconds

        now = time.time()
        elapsed = now - self._last_interjection_time
        return elapsed >= self._cooldown_seconds

    async def _deliver_interjection(self, interjection: Interjection) -> None:
        """Deliver an interjection via TTS and/or WebSocket.

        Args:
            interjection: The interjection to deliver.
        """
        logger.info(f"Delivering interjection: {interjection.message[:50]}...")

        # Update cooldown timestamp
        self._last_interjection_time = time.time()

        # Speak via TTS if enabled
        if interjection.speak:
            try:
                await self._tts_callback(interjection.message, self._language)
            except Exception as e:
                logger.error(f"TTS callback failed: {e}")

        # Broadcast to frontend
        try:
            await self._ws_broadcaster(
                "notification",
                {
                    "id": interjection.id,
                    "message": interjection.message,
                    "severity": interjection.severity,
                    **interjection.notification_payload,
                },
            )
        except Exception as e:
            logger.error(f"WebSocket broadcast failed: {e}")

    def _format_message(
        self,
        template_key: str,
        language: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Format an interjection message using templates.

        Args:
            template_key: Key into INTERJECTION_TEMPLATES.
            language: Language code (default: configured language).
            **kwargs: Format string arguments.

        Returns:
            Formatted message string.
        """
        lang = language or self._language
        templates = INTERJECTION_TEMPLATES.get(template_key, {})
        template = templates.get(lang, templates.get("en", ""))

        if not template:
            logger.warning(f"No template found for '{template_key}'")
            return ""

        try:
            return template.format(**kwargs)
        except KeyError as e:
            logger.error(f"Missing template variable: {e}")
            return template

    # =========================================================================
    # Event handlers
    # =========================================================================

    async def _handle_calendar_event(self, event: Event) -> None:
        """Handle approaching calendar event.

        Args:
            event: Event with payload containing:
                - title: Event title
                - starts_in_minutes: Minutes until event starts
        """
        payload = event.payload
        minutes = payload.get("starts_in_minutes", 10)
        title = payload.get("title", "event")

        # Determine template based on time
        if minutes <= 5:
            template_key = "meeting_reminder_5"
        else:
            template_key = "meeting_reminder_10"

        if not self._can_interject(event_type="calendar_event_approaching"):
            logger.debug("Calendar interjection skipped (cooldown)")
            return

        # Update calendar-specific cooldown timestamp before delivering.
        self._last_calendar_interjection_time = time.time()

        triggers = self._config.get("triggers", {})
        voice_enabled = triggers.get("meeting_reminder", {}).get("voice", True)

        message = self._format_message(template_key, title=title)
        interjection = Interjection(
            message=message,
            severity="info",
            speak=voice_enabled,
            notification_payload={
                "event_type": "calendar",
                "title": title,
                "starts_in_minutes": minutes,
            },
        )

        await self._deliver_interjection(interjection)

    async def _handle_vip_mail(self, event: Event) -> None:
        """Handle VIP mail notification.

        Args:
            event: Event with payload containing:
                - sender: Email sender
                - subject: Email subject
        """
        payload = event.payload
        sender = payload.get("sender", "someone")
        subject = payload.get("subject", "")

        if not self._can_interject():
            logger.debug("VIP mail interjection skipped (cooldown)")
            return

        triggers = self._config.get("triggers", {})
        voice_enabled = triggers.get("vip_mail", {}).get("voice", True)

        message = self._format_message("vip_mail", sender=sender, subject=subject)
        interjection = Interjection(
            message=message,
            severity="info",
            speak=voice_enabled,
            notification_payload={
                "event_type": "email",
                "sender": sender,
                "subject": subject,
            },
        )

        await self._deliver_interjection(interjection)

    async def _handle_repo_dirty(self, event: Event) -> None:
        """Handle dirty repository notification.

        Args:
            event: Event with payload containing:
                - repo: Repository name
                - branch: Branch name
                - idle_minutes: Minutes idle
        """
        payload = event.payload
        repo = payload.get("repo", "repository")
        branch = payload.get("branch", "main")
        minutes = payload.get("idle_minutes", 0)

        if not self._can_interject():
            logger.debug("Dirty repo interjection skipped (cooldown)")
            return

        triggers = self._config.get("triggers", {})
        voice_enabled = triggers.get("dirty_repo", {}).get("voice", False)

        message = self._format_message(
            "dirty_repo",
            repo=repo,
            branch=branch,
            minutes=minutes,
        )
        interjection = Interjection(
            message=message,
            severity="warning",
            speak=voice_enabled,
            notification_payload={
                "event_type": "git",
                "repo": repo,
                "branch": branch,
            },
        )

        await self._deliver_interjection(interjection)

    async def _handle_system_alert(self, event: Event) -> None:
        """Handle system threshold exceeded alert.

        Args:
            event: Event with payload containing:
                - metric: "cpu", "gpu_temp", "disk", etc.
                - value: Current value
                - threshold: Configured threshold
        """
        payload = event.payload
        metric = payload.get("metric", "unknown")
        value = payload.get("value", 0)
        threshold = payload.get("threshold", 0)

        # System alerts are often urgent
        severity = "urgent" if metric == "gpu_temp" and value > 90 else "warning"

        if not self._can_interject(severity):
            logger.debug("System alert interjection skipped (cooldown)")
            return

        triggers = self._config.get("triggers", {})
        voice_enabled = triggers.get("system_alert", {}).get("voice", True)

        # Select template based on metric
        template_map = {
            "cpu": "system_cpu",
            "gpu_temp": "system_gpu_temp",
            "disk": "system_disk",
        }
        template_key = template_map.get(metric, "system_cpu")

        message = self._format_message(
            template_key,
            value=value,
            threshold=threshold,
        )
        interjection = Interjection(
            message=message,
            severity=severity,
            speak=voice_enabled,
            notification_payload={
                "event_type": "system",
                "metric": metric,
                "value": value,
                "threshold": threshold,
            },
        )

        await self._deliver_interjection(interjection)

    async def _handle_late_night(self, event: Event) -> None:
        """Handle late night reminder.

        Args:
            event: Event with payload (optional).
        """
        if not self._can_interject():
            logger.debug("Late night interjection skipped (cooldown)")
            return

        triggers = self._config.get("triggers", {})
        voice_enabled = triggers.get("late_night_reminder", {}).get("voice", True)

        message = self._format_message("late_night")
        interjection = Interjection(
            message=message,
            severity="info",
            speak=voice_enabled,
            notification_payload={"event_type": "reminder"},
        )

        await self._deliver_interjection(interjection)
