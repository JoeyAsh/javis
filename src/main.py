"""Main entry point for JARVIS voice assistant.

Audio is now captured in the browser and streamed to the backend via
WebSocket binary frames (raw Int16 PCM at 16 kHz mono).  All voice
pipeline logic lives in api/ws_server.py.
"""

import asyncio
import signal
import sys
from typing import Any

from dotenv import load_dotenv

from api.ws_server import broadcast_notification, start_ws_server
from brain.proactive import ProactiveScheduler
from utils.config_loader import get_config
from utils.events import Event, EventBus
from utils.logger import get_logger, setup_logger

logger = get_logger("main")

# Module-level handle so other modules (tests, dev triggers, voice pipeline
# agents) can publish events without plumbing the bus through every layer.
event_bus: EventBus | None = None


async def _notification_broadcaster(topic: str, payload: dict[str, Any]) -> None:
    """Bridge the scheduler's ws_broadcaster callback to broadcast_notification.

    The scheduler emits `(topic, payload)` where topic is always
    ``"notification"`` and payload carries id / message / severity plus any
    extra keys merged from ``Interjection.notification_payload``. We unpack
    that into the fields our HUD consumes.
    """
    if topic != "notification":
        logger.debug(f"Unhandled broadcaster topic: {topic}")
        return
    message = payload.get("message", "")
    # Prefer explicit title/detail if the interjection set them; else derive
    # from the message (title = first sentence-ish, detail = full message).
    title = payload.get("title") or (message.split(".")[0] if message else "JARVIS")
    detail = payload.get("detail") or message
    await broadcast_notification(
        notification_id=str(payload.get("id", "")),
        severity=str(payload.get("severity", "info")),
        title=str(title)[:120],
        detail=str(detail),
    )


async def _silent_tts(_text: str, _language: str) -> None:
    """No-op TTS callback — notifications go to HUD only for now.

    Wiring the real Fish Audio TTS path here is a follow-up; it requires the
    same TTS engine used by the voice turn pipeline, which currently lives
    inside ws_server. Keeping this a no-op means proactive notifications
    surface visually without risking feedback loops during dev.
    """
    return None


def _asyncio_exception_handler(
    loop: asyncio.AbstractEventLoop, context: dict[str, Any]
) -> None:
    """Print late-shutdown asyncio exceptions to stderr without touching stdlib logging.

    Avoids re-entering the loguru/Rich/InterceptHandler stack during interpreter
    teardown when sys.meta_path is None.
    """
    msg = context.get("message", "asyncio exception")
    exc = context.get("exception")
    try:
        sys.stderr.write(f"[asyncio] {msg}\n")
        if exc is not None:
            sys.stderr.write(f"  exception: {exc!r}\n")
    except Exception:  # noqa: BLE001
        pass


async def main() -> None:
    """Main entry point.

    Loads configuration, sets up logging, creates shared memory, wires the
    proactive scheduler to the WebSocket notification broadcaster, and
    delegates everything else (wake word, STT, Claude, TTS, WebSocket
    serving) to start_ws_server.
    """
    global event_bus

    load_dotenv()
    config = get_config()

    log_config = config.get_section("logging")
    setup_logger(
        level=log_config.get("level", "INFO"),
        log_file=log_config.get("file"),
    )

    logger.info("Starting JARVIS (browser-mic mode)...")

    # Session memory is owned by OpenClaw (keyed by ``openclaw.session_id``);
    # the transcript archive is the local SQLite ``MemoryStore`` created
    # inside ``start_ws_server``. There is no in-RAM ``ConversationMemory``.
    api_config = config.get_section("api")

    # Proactive-interjection pipeline: a bus for domain events (meeting
    # approaching, VIP mail, system alert, etc.) feeding a Scheduler that
    # forwards curated interjections to the HUD via broadcast_notification.
    event_bus = EventBus()
    proactive_config = config.get_section("proactive")
    persona_config = config.get_section("persona")
    scheduler = ProactiveScheduler(
        event_bus=event_bus,
        config=proactive_config,
        tts_callback=_silent_tts,
        ws_broadcaster=_notification_broadcaster,
        language=persona_config.get("default_language", "de"),
    )

    shutdown_event = asyncio.Event()

    def _signal_handler() -> None:
        logger.info("Shutdown signal received")
        shutdown_event.set()

    loop = asyncio.get_event_loop()
    loop.set_exception_handler(_asyncio_exception_handler)
    if sys.platform != "win32":
        loop.add_signal_handler(signal.SIGINT, _signal_handler)
        loop.add_signal_handler(signal.SIGTERM, _signal_handler)

    try:
        await scheduler.start()

        ws_task = asyncio.create_task(
            start_ws_server(api_config, None, None)
        )

        # Note: the startup "JARVIS online" notification is now emitted
        # per-connection inside ws_server.websocket_handler (stable id
        # means client-side dedup handles reconnects gracefully). Nothing
        # to schedule here.
        ping_task: asyncio.Task[None] | None = None

        # Wait until a shutdown signal is received
        await shutdown_event.wait()

        if ping_task is not None:
            ping_task.cancel()
        ws_task.cancel()
        try:
            await ws_task
        except asyncio.CancelledError:
            pass

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt — shutting down")
    except Exception as exc:
        logger.exception(f"Fatal error: {exc}")
        raise
    finally:
        await scheduler.stop()
        logger.info("JARVIS shutdown complete")


def publish_event(event_type: str, payload: dict[str, Any] | None = None) -> None:
    """Synchronous convenience wrapper — publish an event from anywhere.

    Intended for dev triggers, voice-pipeline hooks, and future integration
    clients (calendar poller, VIP mail watcher, …). No-op if the bus has
    not been initialised yet (e.g. imported before main() runs).
    """
    if event_bus is None:
        logger.warning(
            f"publish_event('{event_type}') called before EventBus init — dropped"
        )
        return
    event = Event(type=event_type, payload=payload or {})
    asyncio.create_task(event_bus.publish(event))


if __name__ == "__main__":
    asyncio.run(main())
