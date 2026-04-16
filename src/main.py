"""Main entry point for JARVIS voice assistant.

Audio is now captured in the browser and streamed to the backend via
WebSocket binary frames (raw Int16 PCM at 16 kHz mono).  All voice
pipeline logic lives in api/ws_server.py.
"""

import asyncio
import signal
import sys

from dotenv import load_dotenv

from api.ws_server import start_ws_server
from brain.memory_legacy import ConversationMemory
from utils.config_loader import get_config
from utils.logger import get_logger, setup_logger

logger = get_logger("main")


async def main() -> None:
    """Main entry point.

    Loads configuration, sets up logging, creates shared memory, and
    delegates everything else (wake word, STT, Claude, TTS, WebSocket
    serving) to start_ws_server.
    """
    load_dotenv()
    config = get_config()

    log_config = config.get_section("logging")
    setup_logger(
        level=log_config.get("level", "INFO"),
        log_file=log_config.get("file"),
    )

    logger.info("Starting JARVIS (browser-mic mode)...")

    claude_config = config.get_section("claude")
    memory = ConversationMemory(
        max_turns=claude_config.get("max_history_turns", 10)
    )

    api_config = config.get_section("api")

    shutdown_event = asyncio.Event()

    def _signal_handler() -> None:
        logger.info("Shutdown signal received")
        shutdown_event.set()

    loop = asyncio.get_event_loop()
    if sys.platform != "win32":
        loop.add_signal_handler(signal.SIGINT, _signal_handler)
        loop.add_signal_handler(signal.SIGTERM, _signal_handler)

    try:
        ws_task = asyncio.create_task(
            start_ws_server(api_config, memory, None)
        )

        # Wait until a shutdown signal is received
        await shutdown_event.wait()

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
        logger.info("JARVIS shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
