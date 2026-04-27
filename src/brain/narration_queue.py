"""NarrationQueue for JARVIS — Phase 2 (#93).

Accepts background narration items (from agents, the briefing pipeline, etc.)
and drains them to TTS only when the conversation state machine is idle.

Phase 2 additions on top of the minimal Phase 1 queue:
  - Quiet mode: ``quiet_until`` timestamp; demotes all items to HUD-only
    except ``urgent`` (which still plays voice but with a soft pre-roll).
  - Per-source rate limiting: deque-of-timestamps per source, default 6/60s.
    Excess items are dropped with a WARN log; one ``urgent`` throttle notice
    fires per throttle event (the notice itself is exempt from rate limiting).
  - Completion batching: when a ``completion`` item arrives, a 10s coalesce
    window is opened. Additional ``completion`` items from the same source
    arriving within that window are merged into one composed utterance.
  - Channel routing: ``info`` → HUD only; ``update`` → HUD + optional voice;
    ``urgent`` → voice + HUD; ``completion`` → voice + HUD (batched).
  - TTL handling: items expired while waiting for idle are dropped from voice
    but the HUD card was already shown at enqueue time.
  - WS broadcast callbacks: ``on_queue_mutation`` is called after every queue
    change so the WS layer can broadcast ``narration_state`` and
    ``activity_panel`` messages to the frontend.
"""

from __future__ import annotations

import asyncio
import collections
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Literal

from brain.conversation_state import ConversationState, ConversationStateMachine
from utils.logger import get_logger

logger = get_logger("narration_queue")

# Default TTL for info-severity items (they expire if not spoken in time).
_INFO_TTL_S: float = 120.0
# No TTL for update/urgent/completion items by default (0 = never expires).
_NO_TTL: float = 0.0

# Pre-emption pre-roll phrases indexed by severity-context.
_PREROLL_URGENT_QUIET = "Verzeihung, Sir — kurz: "
_PREROLL_URGENT_DIALOGUE = "Verzeihung der Unterbrechung, Sir — wichtiger Hinweis: "
_PREROLL_URGENT_QUIET_MODE = "Sir — "

SeverityLiteral = Literal["info", "update", "urgent", "completion"]


@dataclass
class NarrationItem:
    """A single item destined for voice narration and/or HUD display."""

    id: str
    text: str
    severity: SeverityLiteral = "update"
    source: str | None = None
    created_at: float = field(default_factory=time.time)
    ttl_seconds: float = _NO_TTL
    # Channels resolved at enqueue time and updated after quiet-mode check.
    channels: list[str] = field(default_factory=list)


@dataclass
class SourceStatus:
    """Per-source status last set via ``jarvis_set_status``."""

    source: str
    status: Literal["starting", "in_progress", "done", "blocked"]
    message: str | None
    updated_at: float = field(default_factory=time.time)


class NarrationQueue:
    """Prioritised in-memory queue that drains narration items to TTS.

    The drainer task wakes whenever a new item is enqueued or the state
    machine enters IDLE, then emits the next item if conditions allow.

    Only one item is emitted at a time — the drainer awaits the tts_emit
    callback before popping the next item.

    Phase 2 features: quiet mode, per-source rate limiting, completion
    batching, channel-aware routing, WS mutation callbacks.
    """

    def __init__(
        self,
        state_machine: ConversationStateMachine,
        tts_emit: Callable[[str], Awaitable[None]],
        # Phase 2: config values (with defaults matching spec)
        update_voice: bool = False,
        urgent_max_wait_seconds: float = 30.0,
        completion_batch_seconds: float = 10.0,
        rate_limit_items: int = 6,
        rate_limit_window_seconds: float = 60.0,
        quiet_mode_default_minutes: int = 60,
        # Phase 2: WS broadcast callbacks (injected by ws_server)
        on_queue_mutation: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        """Initialise the queue.

        Args:
            state_machine: Shared conversation state machine used to gate
                emission (only emit when state is IDLE).
            tts_emit: Async callable that accepts a plain text string and
                synthesises + broadcasts it through the TTS pipeline.
            update_voice: When True, ``update``-severity items play voice
                in addition to HUD. Default False.
            urgent_max_wait_seconds: How long (seconds) an ``urgent`` item
                waits for idle before firing anyway with a polite pre-roll.
            completion_batch_seconds: Coalesce window (seconds) for batching
                ``completion`` items from the same source.
            rate_limit_items: Maximum items per source within the window.
            rate_limit_window_seconds: Rate-limit time window in seconds.
            quiet_mode_default_minutes: Default quiet mode duration (minutes)
                when no explicit duration is given to ``set_quiet_mode``.
            on_queue_mutation: Optional async callback fired after every queue
                mutation (enqueue / dequeue / quiet toggle / status update).
                Used by the WS layer to trigger narration_state broadcasts.
        """
        self._sm = state_machine
        self._tts_emit = tts_emit
        self._update_voice = update_voice
        self._urgent_max_wait = urgent_max_wait_seconds
        self._completion_batch_s = completion_batch_seconds
        self._rate_limit_items = rate_limit_items
        self._rate_limit_window = rate_limit_window_seconds
        self._quiet_mode_default_minutes = quiet_mode_default_minutes
        self._on_queue_mutation = on_queue_mutation

        self._queue: deque[NarrationItem] = deque()
        self._wake_event: asyncio.Event = asyncio.Event()
        self._drainer_task: asyncio.Task[None] | None = None
        self._running: bool = False

        # Quiet mode
        self._quiet_until: datetime | None = None

        # Per-source rate limiting: source → deque of enqueue timestamps
        self._rate_timestamps: dict[str, deque[float]] = {}
        # Track sources that already received a throttle notice in the current
        # window so we don't flood them with repeated urgent throttle items.
        self._throttle_notified: set[str] = set()

        # Completion batching: source → (batch_items, expiry_task)
        self._completion_batches: dict[str, list[NarrationItem]] = {}
        self._completion_batch_tasks: dict[str, asyncio.Task[None]] = {}

        # Per-source status tracking (for activity_panel WS broadcast)
        self._source_statuses: dict[str, SourceStatus] = {}

        # History ring-buffer: newest-first, capped at 50 items.
        self._history: collections.deque[NarrationItem] = collections.deque(maxlen=50)

    # -----------------------------------------------------------------------
    # Quiet mode
    # -----------------------------------------------------------------------

    def set_quiet_mode(
        self,
        enabled: bool,
        duration_minutes: int | None = None,
    ) -> datetime | None:
        """Enable or disable quiet mode.

        When enabling while already quiet the timer is replaced (not stacked).
        Idempotent: disabling while already not quiet is a no-op.

        Args:
            enabled: True to enter quiet mode, False to leave it.
            duration_minutes: Duration in minutes. Uses the configured default
                when None and enabled=True.

        Returns:
            The new ``quiet_until`` datetime (UTC), or None when disabled.
        """
        if enabled:
            mins = duration_minutes if duration_minutes is not None else self._quiet_mode_default_minutes
            self._quiet_until = datetime.fromtimestamp(
                time.time() + mins * 60, tz=timezone.utc
            )
            logger.info(f"NarrationQueue: quiet mode ON until {self._quiet_until.isoformat()}")
        else:
            self._quiet_until = None
            logger.info("NarrationQueue: quiet mode OFF")
        asyncio.ensure_future(self._fire_mutation())
        return self._quiet_until

    @property
    def is_quiet(self) -> bool:
        """Return True when quiet mode is currently active."""
        if self._quiet_until is None:
            return False
        if datetime.now(timezone.utc) >= self._quiet_until:
            # Expired — clear lazily
            self._quiet_until = None
            return False
        return True

    @property
    def quiet_until(self) -> datetime | None:
        """Return the quiet-mode expiry (UTC) or None."""
        if self._quiet_until is None:
            return None
        if datetime.now(timezone.utc) >= self._quiet_until:
            self._quiet_until = None
        return self._quiet_until

    # -----------------------------------------------------------------------
    # Status tracking (jarvis_set_status)
    # -----------------------------------------------------------------------

    def set_source_status(
        self,
        source: str,
        status: Literal["starting", "in_progress", "done", "blocked"],
        message: str | None = None,
    ) -> SourceStatus | None:
        """Coalesce per-source progress status.

        Replaces any prior status from the same source.

        Args:
            source: Source identifier (e.g. ``"claude-code-91"``).
            status: One of ``starting``, ``in_progress``, ``done``, ``blocked``.
            message: Optional human-readable status message.

        Returns:
            The prior :class:`SourceStatus` for this source, or None.
        """
        prior = self._source_statuses.get(source)
        self._source_statuses[source] = SourceStatus(
            source=source,
            status=status,
            message=message,
        )
        logger.debug(f"NarrationQueue: source status [{source}] → {status!r}")
        asyncio.ensure_future(self._fire_mutation())
        return prior

    def get_source_statuses(self) -> dict[str, dict[str, Any]]:
        """Return all known source statuses, keyed by source name."""
        return {
            s.source: {
                "status": s.status,
                "message": s.message,
                "updated_at": datetime.fromtimestamp(s.updated_at, tz=timezone.utc).isoformat(),
            }
            for s in self._source_statuses.values()
        }

    def get_history(self) -> list[dict[str, Any]]:
        """Return the narration history (newest first, max 50) as serialisable dicts."""
        return [
            {
                "id": it.id,
                "text": it.text,
                "severity": it.severity,
                "source": it.source,
                "created_at": datetime.fromtimestamp(it.created_at, tz=timezone.utc).isoformat(),
                "ttl_seconds": it.ttl_seconds if it.ttl_seconds > 0 else None,
            }
            for it in self._history
        ]

    # -----------------------------------------------------------------------
    # Queue state snapshot (for WS broadcast)
    # -----------------------------------------------------------------------

    def get_state_snapshot(self) -> dict[str, Any]:
        """Return a serialisable snapshot of the queue state.

        Used by the WS layer to build the ``narration_state`` broadcast payload.
        """
        items = [
            {
                "id": it.id,
                "text": it.text,
                "severity": it.severity,
                "source": it.source,
                "created_at": datetime.fromtimestamp(
                    it.created_at, tz=timezone.utc
                ).isoformat(),
                "channels": it.channels,
            }
            for it in self._queue
        ]
        qu = self.quiet_until
        return {
            "state": self._sm.state.value,
            "quiet_until": qu.isoformat() if qu is not None else None,
            "items": items,
        }

    # -----------------------------------------------------------------------
    # Rate limiting (internal)
    # -----------------------------------------------------------------------

    def _check_rate_limit(self, source: str) -> bool:
        """Return True when the item may be enqueued; False when throttled.

        Maintains a sliding deque of enqueue timestamps per source. If the
        deque already holds ``rate_limit_items`` within the window, the item
        is rejected. A single ``urgent`` throttle notice is enqueued (exempt
        from rate limiting itself) the first time a source is throttled.

        Args:
            source: The item's source tag.

        Returns:
            True if allowed, False if throttled.
        """
        now = time.time()
        window_start = now - self._rate_limit_window

        if source not in self._rate_timestamps:
            self._rate_timestamps[source] = deque()
        ts_deque = self._rate_timestamps[source]

        # Evict timestamps outside the window.
        while ts_deque and ts_deque[0] < window_start:
            ts_deque.popleft()

        if len(ts_deque) >= self._rate_limit_items:
            # Throttled — fire one urgent notice if not already done.
            if source not in self._throttle_notified:
                self._throttle_notified.add(source)
                logger.warning(
                    f"NarrationQueue: source {source!r} throttled "
                    f"({self._rate_limit_items} items/{self._rate_limit_window:.0f}s)"
                )
                # Enqueue a throttle notice exempt from rate limiting.
                notice = NarrationItem(
                    id=f"narr-throttle-{uuid.uuid4().hex[:8]}",
                    text=f"Quelle {source} ist gedrosselt.",
                    severity="urgent",
                    source=source,
                    created_at=time.time(),
                    ttl_seconds=_NO_TTL,
                    channels=["voice", "hud"],
                )
                self._queue.appendleft(notice)
                self._wake_event.set()
                asyncio.ensure_future(self._fire_mutation())
            return False

        # Within limit — record this timestamp.
        ts_deque.append(now)
        # Reset throttle-notice sentinel when the source recovers.
        self._throttle_notified.discard(source)
        return True

    # -----------------------------------------------------------------------
    # Completion batching (internal)
    # -----------------------------------------------------------------------

    def _accept_completion(self, item: NarrationItem) -> bool:
        """Route a ``completion`` item into the coalesce buffer.

        Opens (or extends) a 10s coalesce window per source. Returns True
        to indicate the item was accepted into the buffer (not the main queue).

        Args:
            item: The ``completion`` NarrationItem to batch.

        Returns:
            Always True — the item is held in the batch buffer.
        """
        src = item.source or "__default__"
        if src not in self._completion_batches:
            self._completion_batches[src] = []
        self._completion_batches[src].append(item)

        # Cancel the previous flush task (if any) to extend the window.
        existing = self._completion_batch_tasks.get(src)
        if existing is not None and not existing.done():
            existing.cancel()

        task = asyncio.ensure_future(self._flush_completion_batch_after(src))
        self._completion_batch_tasks[src] = task
        return True

    async def _flush_completion_batch_after(self, source: str) -> None:
        """Wait for the coalesce window then flush the batch to the main queue.

        Args:
            source: The source key whose batch window just closed.
        """
        try:
            await asyncio.sleep(self._completion_batch_s)
        except asyncio.CancelledError:
            return  # Window extended — new task will flush later.

        batch = self._completion_batches.pop(source, [])
        self._completion_batch_tasks.pop(source, None)
        if not batch:
            return

        if len(batch) == 1:
            composed_text = batch[0].text
        else:
            composed_text = " ".join(it.text for it in batch)

        composed = NarrationItem(
            id=f"narr-batch-{uuid.uuid4().hex[:8]}",
            text=composed_text,
            severity="completion",
            source=batch[0].source,
            created_at=time.time(),
            ttl_seconds=_NO_TTL,
            channels=["voice", "hud"],
        )
        self._queue.append(composed)
        logger.debug(
            f"NarrationQueue: completion batch flushed for source={source!r} "
            f"({len(batch)} item(s)) → {composed.id!r}"
        )
        self._wake_event.set()
        asyncio.ensure_future(self._fire_mutation())

    # -----------------------------------------------------------------------
    # Mutation callback
    # -----------------------------------------------------------------------

    async def _fire_mutation(self) -> None:
        """Call the on_queue_mutation callback if set; silently skip on error."""
        if self._on_queue_mutation is not None:
            try:
                await self._on_queue_mutation()
            except Exception as exc:
                logger.warning(f"NarrationQueue: on_queue_mutation callback error: {exc}")

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def enqueue(
        self,
        text: str,
        severity: SeverityLiteral = "update",
        source: str | None = None,
        ttl_seconds: float = _NO_TTL,
    ) -> str:
        """Add a narration item to the queue.

        Applies rate limiting (per source), completion batching, and channel
        routing before inserting into the priority queue.

        Args:
            text: Plain-text string for TTS synthesis.
            severity: Priority level; ``urgent`` inserts at the front.
            source: Optional source tag for rate limiting / batching.
            ttl_seconds: Seconds after creation before the item is silently
                dropped. 0 means never expires.

        Returns:
            The generated item id.
        """
        item_id = f"narr-{uuid.uuid4().hex[:8]}"

        # Rate limiting (skip for system-generated throttle notices).
        if source is not None:
            if not self._check_rate_limit(source):
                logger.warning(
                    f"NarrationQueue: item from source={source!r} dropped (rate limited)"
                )
                return item_id

        # Resolve channels based on severity and quiet mode.
        channels = self._resolve_channels(severity)

        item = NarrationItem(
            id=item_id,
            text=text,
            severity=severity,
            source=source,
            created_at=time.time(),
            ttl_seconds=ttl_seconds if ttl_seconds > 0 else _NO_TTL,
            channels=channels,
        )

        # Completion batching — route into coalesce buffer, not main queue.
        if severity == "completion":
            self._history.appendleft(item)
            self._accept_completion(item)
            logger.debug(
                f"NarrationQueue: [{severity}] {item.id!r} → completion batch buffer"
                + (f" source={source!r}" if source else "")
            )
            asyncio.ensure_future(self._fire_mutation())
            return item_id

        # Standard queue insertion.
        self._history.appendleft(item)
        if severity == "urgent":
            self._queue.appendleft(item)
        else:
            self._queue.append(item)

        logger.debug(
            f"NarrationQueue enqueued [{item.severity}] {item.id!r}"
            + (f" source={source!r}" if source else "")
            + f" channels={channels}"
        )
        self._wake_event.set()
        asyncio.ensure_future(self._fire_mutation())
        return item_id

    def speak_now(
        self,
        text: str,
        severity: SeverityLiteral = "update",
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
        # Cancel any pending completion batch flush tasks.
        for task in self._completion_batch_tasks.values():
            if not task.done():
                task.cancel()
        self._completion_batch_tasks.clear()
        logger.info("NarrationQueue drainer stopped")

    # -----------------------------------------------------------------------
    # Channel routing
    # -----------------------------------------------------------------------

    def _resolve_channels(self, severity: SeverityLiteral) -> list[str]:
        """Resolve the delivery channels for a given severity and quiet state.

        Channel routing rules:
          - ``info`` → HUD card only (no voice, even outside quiet mode).
          - ``update`` → HUD + voice only if ``update_voice`` config is True;
            in quiet mode voice is suppressed.
          - ``urgent`` → voice + HUD; in quiet mode voice fires with soft pre-roll.
          - ``completion`` → voice + HUD; in quiet mode voice is suppressed.

        Quiet mode demotes all but ``urgent`` to HUD-only.

        Args:
            severity: Item severity string.

        Returns:
            List of channel strings, e.g. ``["hud"]`` or ``["voice", "hud"]``.
        """
        quiet = self.is_quiet

        if severity == "info":
            return ["hud"]

        if severity == "update":
            if quiet:
                return ["hud"]
            return ["voice", "hud"] if self._update_voice else ["hud"]

        if severity == "urgent":
            # Urgent always fires voice, even in quiet mode (spec: fires with
            # softer pre-roll).
            return ["voice", "hud"]

        if severity == "completion":
            if quiet:
                return ["hud"]
            return ["voice", "hud"]

        return ["hud"]

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

                # TTL check: drop expired items silently (HUD already shown).
                if item.ttl_seconds > 0 and (time.time() - item.created_at) > item.ttl_seconds:
                    self._queue.popleft()
                    logger.debug(
                        f"NarrationQueue dropped expired item {item.id!r} "
                        f"(TTL={item.ttl_seconds:.0f}s)"
                    )
                    continue

                # Re-resolve channels at drain time (quiet mode may have
                # changed since the item was enqueued).
                item.channels = self._resolve_channels(item.severity)

                # Determine whether voice delivery is wanted.
                wants_voice = "voice" in item.channels

                if not wants_voice:
                    # HUD-only item: pop and continue (HUD was already shown at
                    # enqueue via the mutation broadcast).
                    self._queue.popleft()
                    logger.debug(
                        f"NarrationQueue: [{item.severity}] {item.id!r} HUD-only, skipping TTS"
                    )
                    continue

                # State-gated voice delivery.
                if self._sm.state == ConversationState.IDLE:
                    pass  # ready to emit
                elif item.severity == "urgent":
                    # Urgent: wait up to urgent_max_wait_seconds for idle;
                    # if active_dialogue is still running after that, fire anyway.
                    reached_idle = await self._sm.wait_for_idle(
                        timeout=self._urgent_max_wait
                    )
                    if not reached_idle:
                        logger.warning(
                            f"Urgent item {item.id!r} waited {self._urgent_max_wait:.0f}s "
                            "for idle — emitting with polite pre-roll"
                        )
                        # Apply the more polite long pre-roll for dialogue interruption.
                        item.text = _PREROLL_URGENT_DIALOGUE + item.text
                    # If we are in quiet mode now, use the soft pre-roll.
                    elif self.is_quiet:
                        item.text = _PREROLL_URGENT_QUIET_MODE + item.text
                    else:
                        item.text = _PREROLL_URGENT_QUIET + item.text
                else:
                    # info/update/completion wait indefinitely.
                    # If TTL expires while waiting, the item will be dropped on
                    # next iteration.
                    await self._sm.wait_for_idle(timeout=None)
                    continue  # re-evaluate queue head after waking

                # Re-check queue (may have been emptied concurrently).
                if not self._queue:
                    continue

                item = self._queue.popleft()

                # Re-check TTL after potentially long wait.
                if item.ttl_seconds > 0 and (time.time() - item.created_at) > item.ttl_seconds:
                    logger.debug(
                        f"NarrationQueue dropped expired item {item.id!r} (post-wait)"
                    )
                    # HUD card already shown; skip voice only.
                    continue

                # Re-resolve channels one last time after any waits.
                item.channels = self._resolve_channels(item.severity)
                if "voice" not in item.channels:
                    logger.debug(
                        f"NarrationQueue: [{item.severity}] {item.id!r} "
                        "demoted to HUD-only after wait (quiet mode engaged)"
                    )
                    continue

                logger.debug(f"NarrationQueue emitting [{item.severity}] {item.id!r}")
                try:
                    await self._tts_emit(item.text)
                except Exception as exc:
                    logger.warning(f"NarrationQueue tts_emit failed for {item.id!r}: {exc}")

        except asyncio.CancelledError:
            logger.debug("NarrationQueue drain_loop cancelled cleanly")
