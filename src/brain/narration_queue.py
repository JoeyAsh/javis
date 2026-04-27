"""Minimal NarrationQueue for JARVIS — Phase 1 (#93).

Accepts background narration items (from agents, the briefing pipeline, etc.)
and drains them to TTS only when the conversation state machine is idle.
Urgent items jump to the front of the queue but still wait for any current
TTS to finish before emitting (sentence-boundary pre-emption is deferred to
#93 Phase 2).
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Literal

from brain.conversation_state import ConversationState, ConversationStateMachine
from utils.logger import get_logger

logger = get_logger("narration_queue")

# Default TTL for info-severity items (they expire if not spoken in time).
_INFO_TTL_S: float = 120.0
# No TTL for update/urgent/completion items by default (0 = never expires).
_NO_TTL: float = 0.0


@dataclass
class NarrationItem:
    """A single item destined for voice narration."""

    id: str
    text: str
    severity: Literal["info", "update", "urgent", "completion"] = "update"
    source: str | None = None
    created_at: float = field(default_factory=time.time)
    ttl_seconds: float = _NO_TTL


class NarrationQueue:
    """Prioritised in-memory queue that drains narration items to TTS.

    The drainer task wakes whenever a new item is enqueued or the state
    machine enters IDLE, then emits the next item if conditions allow.

    Only one item is emitted at a time — the drainer awaits the tts_emit
    callback before popping the next item.
    """

    def __init__(
        self,
        state_machine: ConversationStateMachine,
        tts_emit: Callable[[str], Awaitable[None]],
    ) -> None:
        """Initialise the queue.

        Args:
            state_machine: Shared conversation state machine used to gate
                emission (only emit when state is IDLE).
            tts_emit: Async callable that accepts a plain text string and
                synthesises + broadcasts it through the TTS pipeline.
        """
        self._sm = state_machine
        self._tts_emit = tts_emit
        self._queue: deque[NarrationItem] = deque()
        self._wake_event: asyncio.Event = asyncio.Event()
        self._drainer_task: asyncio.Task[None] | None = None
        self._running: bool = False

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def enqueue(
        self,
        text: str,
        severity: Literal["info", "update", "urgent", "completion"] = "update",
        source: str | None = None,
        ttl_seconds: float = _NO_TTL,
    ) -> str:
        """Add a narration item to the queue.

        Args:
            text: Plain-text string for TTS synthesis.
            severity: Priority level; ``urgent`` inserts at the front.
            source: Optional source tag for logging / deduplication.
            ttl_seconds: Seconds after creation before the item is silently
                dropped. 0 means never expires.

        Returns:
            The generated item id.
        """
        item = NarrationItem(
            id=f"narr-{uuid.uuid4().hex[:8]}",
            text=text,
            severity=severity,
            source=source,
            created_at=time.time(),
            ttl_seconds=ttl_seconds if ttl_seconds > 0 else _NO_TTL,
        )
        if severity == "urgent":
            self._queue.appendleft(item)
        else:
            self._queue.append(item)
        logger.debug(
            f"NarrationQueue enqueued [{item.severity}] {item.id!r}"
            + (f" source={source!r}" if source else "")
        )
        self._wake_event.set()
        return item.id

    def speak_now(
        self,
        text: str,
        severity: Literal["info", "update", "urgent", "completion"] = "update",
        source: str | None = None,
        ttl_seconds: float = _NO_TTL,
    ) -> str:
        """Preferred public alias for :meth:`enqueue`.

        Args:
            text: Plain-text string for TTS synthesis.
            severity: Priority level.
            source: Optional source tag.
            ttl_seconds: Item TTL in seconds (0 = no expiry).

        Returns:
            The generated item id.
        """
        return self.enqueue(text, severity=severity, source=source, ttl_seconds=ttl_seconds)

    def start(self) -> None:
        """Launch the background drainer task."""
        if self._running:
            return
        self._running = True
        self._drainer_task = asyncio.ensure_future(self._drain_loop())
        logger.info("NarrationQueue drainer started")

    def stop(self) -> None:
        """Cancel the background drainer task cleanly."""
        self._running = False
        if self._drainer_task is not None and not self._drainer_task.done():
            self._drainer_task.cancel()
        logger.info("NarrationQueue drainer stopped")

    # -----------------------------------------------------------------------
    # Drainer
    # -----------------------------------------------------------------------

    async def _drain_loop(self) -> None:
        """Background loop: wait for items and emit them when state allows."""
        try:
            while self._running:
                # Block until a new item arrives or the state transitions.
                self._wake_event.clear()

                if not self._queue:
                    await self._wake_event.wait()
                    continue

                item = self._queue[0]

                # TTL check: drop expired items silently.
                if item.ttl_seconds > 0 and (time.time() - item.created_at) > item.ttl_seconds:
                    self._queue.popleft()
                    logger.debug(f"NarrationQueue dropped expired item {item.id!r}")
                    continue

                # Urgent items wait for SPEAKING to finish (max 30 s).
                # Info/update/completion all wait for IDLE unconditionally.
                if self._sm.state == ConversationState.IDLE:
                    pass  # ready to emit
                elif item.severity == "urgent" and self._sm.state == ConversationState.SPEAKING:
                    # Wait up to 30 s for current TTS to finish.
                    reached_idle = await self._sm.wait_for_idle(timeout=30.0)
                    if not reached_idle:
                        logger.warning(
                            f"Urgent item {item.id!r} waited 30 s for idle — emitting anyway"
                        )
                else:
                    # Wait indefinitely for idle.
                    await self._sm.wait_for_idle(timeout=None)
                    continue  # re-evaluate queue head after waking

                # Re-check queue (may have been emptied by stop() or concurrent code).
                if not self._queue:
                    continue

                item = self._queue.popleft()

                # Re-check TTL after potentially long wait.
                if item.ttl_seconds > 0 and (time.time() - item.created_at) > item.ttl_seconds:
                    logger.debug(f"NarrationQueue dropped expired item {item.id!r} (post-wait)")
                    continue

                logger.debug(f"NarrationQueue emitting [{item.severity}] {item.id!r}")
                try:
                    await self._tts_emit(item.text)
                except Exception as exc:
                    logger.warning(f"NarrationQueue tts_emit failed for {item.id!r}: {exc}")

                # After emitting, loop immediately so chained items don't
                # insert an artificial pause beyond the state-machine's own
                # TTS silence buffer (500 ms).

        except asyncio.CancelledError:
            logger.debug("NarrationQueue drain_loop cancelled cleanly")
