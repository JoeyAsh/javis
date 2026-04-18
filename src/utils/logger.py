"""Logging configuration for JARVIS.

Uses loguru for structured logging with file and console output.
The module also exposes a loguru *sink* that fans log records out to all
connected WebSocket clients as ``log_line`` JSON frames.  The sink is
non-blocking: it enqueues onto an ``asyncio.Queue`` and a background task
drains that queue so the loguru thread (or the event-loop thread that emits
the record) is never blocked by network I/O.

Infinite-recursion guard: the broadcast task itself uses only
``print()``-level console output (never loguru) so that a failure in
the broadcaster does not trigger another log record that would re-enter
the broadcaster.
"""

import asyncio
import sys
import time
from collections import deque
from pathlib import Path
from typing import Any

from loguru import logger

# ---------------------------------------------------------------------------
# Log-panel ring buffer  (server-side)
# ---------------------------------------------------------------------------

# Populated from config at sink-registration time; default matches the
# config.yaml default so the guard works before config is loaded.
_max_buffer_lines: int = 500

# Ring buffer of the last N log lines (for on-connect replay).
_log_buffer: deque[dict[str, Any]] = deque(maxlen=_max_buffer_lines)

# asyncio.Queue used to hand records from the loguru sink to the broadcast task.
# Typed as Queue[dict] but loguru delivers serialised records to the sink.
_log_queue: asyncio.Queue[dict[str, Any]] | None = None

# Reference to the broadcast function (set by ws_server at startup to avoid a
# circular import).  Signature: async (message: str) -> None.
_ws_broadcast: Any = None  # Callable[[str], Coroutine] | None

# Set to True while the background drainer task is running so we don't
# launch it more than once.
_drainer_running: bool = False


def register_ws_broadcast(broadcast_fn: Any, max_buffer: int = 500) -> None:
    """Wire up the WS log sink.

    Must be called once from ``ws_server.start_ws_server`` *after* the
    asyncio event loop is running so that ``asyncio.Queue`` is bound to
    the correct loop.

    Args:
        broadcast_fn: Async callable ``(message: str) -> None`` that fans
            a JSON string out to all connected WS clients.
        max_buffer: Server-side ring buffer size (lines).
    """
    global _ws_broadcast, _log_queue, _max_buffer_lines, _log_buffer, _drainer_running

    _ws_broadcast = broadcast_fn
    _max_buffer_lines = max_buffer
    _log_buffer = deque(maxlen=max_buffer)
    _log_queue = asyncio.Queue()
    _drainer_running = False

    # Add the loguru sink — runs synchronously inside whatever thread emitted
    # the record, so it must be instant (queue-only, no I/O).
    logger.add(_ws_sink, format="{message}", level="DEBUG", filter=_no_recursion_filter)

    # Launch the background drainer on the current running loop.
    try:
        loop = asyncio.get_event_loop()
        loop.create_task(_drainer_task())
        _drainer_running = True
    except RuntimeError:
        # No running event loop yet — caller will need to ensure the drainer
        # is started separately.  This path should not occur in normal startup.
        pass


def get_log_buffer() -> list[dict[str, Any]]:
    """Return a snapshot of the current server-side log ring buffer.

    Used by the WS handler to replay buffered lines to a newly connected client.

    Returns:
        List of log-line dicts (oldest first), each with keys
        ``timestamp``, ``level``, ``module``, ``message``.
    """
    return list(_log_buffer)


# ---------------------------------------------------------------------------
# Loguru sink implementation
# ---------------------------------------------------------------------------

# Flag used to suppress log records emitted *by the broadcaster itself*
# so we never recurse.
_in_broadcast: bool = False


def _no_recursion_filter(record: Any) -> bool:
    """Loguru filter: skip records emitted from inside the broadcast path."""
    return not _in_broadcast


def _ws_sink(message: Any) -> None:
    """Loguru sink — called synchronously for each log record.

    Builds a ``log_line`` payload dict from the loguru ``record`` and
    puts it on ``_log_queue`` without blocking.
    """
    if _log_queue is None:
        return

    record = message.record
    payload: dict[str, Any] = {
        "timestamp": record["time"].timestamp() * 1000,  # epoch ms
        "level": record["level"].name,
        "module": record["name"] or "",
        "message": record["message"],
    }

    # Append to server-side ring buffer (thread-safe for CPython because
    # deque.append is atomic in CPython; in production we only have one thread
    # calling loguru sinks at a time anyway).
    _log_buffer.append(payload)

    # Non-blocking put: drop if the queue is full (shouldn't happen in practice
    # but we must not block inside a loguru sink).
    try:
        _log_queue.put_nowait(payload)
    except asyncio.QueueFull:
        pass


async def _drainer_task() -> None:
    """Background task: drain ``_log_queue`` and broadcast each record.

    Uses ``print()`` for its own error output so that failures here do not
    trigger new loguru records and cause infinite recursion.
    """
    global _in_broadcast

    if _log_queue is None:
        return

    import json

    while True:
        try:
            payload = await _log_queue.get()
        except asyncio.CancelledError:
            return

        if _ws_broadcast is None:
            continue

        _in_broadcast = True
        try:
            message = json.dumps({"type": "log_line", "payload": payload})
            await _ws_broadcast(message)
        except Exception as exc:  # noqa: BLE001
            print(f"[log-drainer] broadcast error: {exc}", file=sys.stderr)
        finally:
            _in_broadcast = False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def setup_logger(
    level: str = "INFO",
    log_file: str | None = None,
    rotation: str = "10 MB",
    retention: str = "7 days",
) -> None:
    """Configure the global logger.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file. If None, logs to console only.
        rotation: Log file rotation size/time
        retention: How long to keep old log files
    """
    # Remove default handler
    logger.remove()

    # Console handler with color
    logger.add(
        sys.stderr,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ),
        level=level,
        colorize=True,
    )

    # File handler
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        logger.add(
            log_file,
            format=(
                "{time:YYYY-MM-DD HH:mm:ss} | "
                "{level: <8} | "
                "{name}:{function}:{line} | "
                "{message}"
            ),
            level=level,
            rotation=rotation,
            retention=retention,
            compression="zip",
        )

    logger.info(f"Logger initialized with level={level}")


def get_logger(name: str | None = None) -> Any:
    """Get a logger instance.

    Args:
        name: Optional logger name for context

    Returns:
        Logger instance bound with name context
    """
    if name:
        return logger.bind(name=name)
    return logger


# Convenience exports
__all__ = [
    "setup_logger",
    "get_logger",
    "logger",
    "register_ws_broadcast",
    "get_log_buffer",
]
