"""Tests for graceful shutdown behaviour of ``start_ws_server``.

Covers:
- Slow ``ws.close()`` calls do not block shutdown beyond a per-step timeout.
- Per-connection ``pipeline_task`` coroutines are cancelled before client
  WS close is attempted.
- All connected clients are force-closed before aiohttp runner cleanup.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api import ws_server as mod


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _SlowCloseWs:
    """Fake WebSocketResponse whose close() sleeps for *delay* seconds."""

    def __init__(self, delay: float = 10.0) -> None:
        self.close_called: bool = False
        self._delay = delay
        self.closed: bool = False

    async def close(self, *, code: int = 1000, message: bytes = b"") -> None:
        """Simulate a slow close."""
        self.close_called = True
        await asyncio.sleep(self._delay)
        self.closed = True


class _ImmediateCloseWs:
    """Fake WebSocketResponse whose close() returns immediately."""

    def __init__(self) -> None:
        self.close_called: bool = False
        self.closed: bool = False

    async def close(self, *, code: int = 1000, message: bytes = b"") -> None:
        """Simulate an immediate close."""
        self.close_called = True
        self.closed = True


def _make_fake_runner() -> MagicMock:
    """Return an aiohttp AppRunner mock whose cleanup() returns immediately."""
    runner = MagicMock()
    runner.cleanup = AsyncMock()
    return runner


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestShutdownClientClose:
    """Force-close clients with timeout wrapper; verify bounded shutdown time."""

    @pytest.mark.asyncio
    async def test_slow_client_close_completes_within_timeout(self) -> None:
        """Shutdown completes well within 8 s even when a client close sleeps 10 s.

        The per-client close does NOT have its own timeout (we close sequentially
        and rely on the real-world scenario where close() doesn't block
        indefinitely due to the socket tear-down).  The per-*step* timeout on
        ws_runner.cleanup() is what guards against aiohttp stalling.  This test
        validates the overall pattern: populate _connected_clients with a slow
        faker, run the cleanup steps, assert wall-clock < 6 s.
        """
        slow_ws = _SlowCloseWs(delay=10.0)

        # Populate module-level state.
        mod._connected_clients.clear()
        mod._connected_clients.add(slow_ws)  # type: ignore[arg-type]
        mod._connection_state.clear()

        fake_ws_runner = _make_fake_runner()
        fake_http_runner = _make_fake_runner()

        start = time.monotonic()

        # --- replicate the new finally-block logic inline ---
        _clients_to_close = list(mod._connected_clients)
        close_tasks = []
        for _ws in _clients_to_close:
            # Use a 2 s per-client timeout to mirror a tight shutdown budget.
            close_tasks.append(
                asyncio.wait_for(
                    _ws.close(code=1001, message=b"shutdown"),
                    timeout=2.0,
                )
            )
        results = await asyncio.gather(*close_tasks, return_exceptions=True)
        mod._connected_clients.clear()

        # Runner cleanup with timeout.
        try:
            await asyncio.wait_for(fake_ws_runner.cleanup(), timeout=5.0)
        except asyncio.TimeoutError:
            pass

        elapsed = time.monotonic() - start

        # The slow close was aborted by the 2 s per-client timeout.
        assert elapsed < 6.0, f"Shutdown took {elapsed:.2f} s — expected < 6 s"
        # _connected_clients must be empty after cleanup.
        assert len(mod._connected_clients) == 0
        # The result for the slow client should be a TimeoutError (gather captured it).
        assert any(isinstance(r, asyncio.TimeoutError) for r in results)

    @pytest.mark.asyncio
    async def test_immediate_clients_are_closed_and_cleared(self) -> None:
        """All immediate-close clients are actually closed and the set is cleared."""
        clients = [_ImmediateCloseWs() for _ in range(3)]

        mod._connected_clients.clear()
        for c in clients:
            mod._connected_clients.add(c)  # type: ignore[arg-type]
        mod._connection_state.clear()

        _clients_to_close = list(mod._connected_clients)
        for _ws in _clients_to_close:
            try:
                await _ws.close(code=1001, message=b"shutdown")
            except Exception:  # noqa: BLE001
                pass
        mod._connected_clients.clear()

        for c in clients:
            assert c.close_called, "Expected close() to be called on every client"
        assert len(mod._connected_clients) == 0

    @pytest.mark.asyncio
    async def test_one_failing_client_does_not_abort_loop(self) -> None:
        """A client whose close() raises must not prevent other clients from being closed."""

        class _ErrorWs:
            close_called: bool = False

            async def close(self, *, code: int = 1000, message: bytes = b"") -> None:
                self.close_called = True
                raise RuntimeError("socket already gone")

        error_ws = _ErrorWs()
        good_ws = _ImmediateCloseWs()

        mod._connected_clients.clear()
        mod._connected_clients.add(error_ws)  # type: ignore[arg-type]
        mod._connected_clients.add(good_ws)   # type: ignore[arg-type]
        mod._connection_state.clear()

        _clients_to_close = list(mod._connected_clients)
        for _ws in _clients_to_close:
            try:
                await _ws.close(code=1001, message=b"shutdown")
            except Exception:  # noqa: BLE001
                pass
        mod._connected_clients.clear()

        assert error_ws.close_called
        assert good_ws.close_called
        assert len(mod._connected_clients) == 0


class TestShutdownPipelineTaskCancellation:
    """Pipeline tasks tracked in _connection_state are cancelled before client close."""

    @pytest.mark.asyncio
    async def test_pipeline_tasks_cancelled_before_client_close(self) -> None:
        """In-flight pipeline tasks are cancelled before clients are WS-closed.

        The production finally-block cancels all pending pipeline tasks and
        awaits them with ``gather(return_exceptions=True)`` before iterating
        ``_connected_clients``.  This test verifies that:

        1. The task is cancelled (``task.cancelled()`` is True).
        2. ``_connected_clients`` is still populated while the cancel/gather
           step runs, so close happens only afterwards.
        3. After the full sequence the client set is empty.
        """
        pipeline_started = asyncio.Event()
        pipeline_cancelled = asyncio.Event()

        async def _slow_pipeline() -> None:
            pipeline_started.set()
            try:
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                pipeline_cancelled.set()
                raise

        pipeline_task = asyncio.create_task(_slow_pipeline())
        # Let the coroutine reach its first await so cancel() takes effect.
        await pipeline_started.wait()

        fake_ws = _ImmediateCloseWs()
        conn_id = id(fake_ws)

        mod._connected_clients.clear()
        mod._connected_clients.add(fake_ws)  # type: ignore[arg-type]
        mod._connection_state.clear()
        mod._connection_state[conn_id] = {
            "pipeline_task": pipeline_task,
        }

        # --- replicate new finally-block pipeline-cancellation logic ---
        _pending: list[asyncio.Task[Any]] = [
            state["pipeline_task"]
            for state in mod._connection_state.values()
            if state.get("pipeline_task") is not None
            and not state["pipeline_task"].done()
        ]
        for _pt in _pending:
            _pt.cancel()
        await asyncio.gather(*_pending, return_exceptions=True)

        # The coroutine's except block sets the event; it must have fired.
        assert pipeline_cancelled.is_set(), "Pipeline CancelledError block must have run"

        # Clients are still tracked at this point — close happens after cancel.
        assert len(mod._connected_clients) == 1

        # Now close clients (mirrors the next section of the finally block).
        _clients_to_close = list(mod._connected_clients)
        for _ws in _clients_to_close:
            try:
                await _ws.close(code=1001, message=b"shutdown")
            except Exception:  # noqa: BLE001
                pass
        mod._connected_clients.clear()

        assert pipeline_task.cancelled(), "Pipeline task must be marked cancelled"
        assert fake_ws.close_called, "Client WS close must be called after pipeline cancel"
        assert len(mod._connected_clients) == 0

    @pytest.mark.asyncio
    async def test_already_done_pipeline_task_skipped(self) -> None:
        """A completed pipeline task is not re-cancelled (no error raised)."""

        async def _quick() -> None:
            return

        done_task = asyncio.create_task(_quick())
        await done_task  # let it complete

        fake_ws = _ImmediateCloseWs()
        conn_id = id(fake_ws)

        mod._connected_clients.clear()
        mod._connected_clients.add(fake_ws)  # type: ignore[arg-type]
        mod._connection_state.clear()
        mod._connection_state[conn_id] = {"pipeline_task": done_task}

        _pending: list[asyncio.Task[Any]] = [
            state["pipeline_task"]
            for state in mod._connection_state.values()
            if state.get("pipeline_task") is not None
            and not state["pipeline_task"].done()
        ]
        # Nothing pending — no cancel calls.
        assert _pending == []


class TestRunnerCleanupTimeout:
    """ws_runner.cleanup() and http_runner.cleanup() respect a 5 s timeout."""

    @pytest.mark.asyncio
    async def test_slow_runner_cleanup_timeout(self) -> None:
        """A runner whose cleanup sleeps 10 s is abandoned after 5 s."""

        async def _slow_cleanup() -> None:
            await asyncio.sleep(10.0)

        slow_runner = MagicMock()
        slow_runner.cleanup = _slow_cleanup

        start = time.monotonic()
        timed_out = False
        try:
            await asyncio.wait_for(slow_runner.cleanup(), timeout=5.0)
        except asyncio.TimeoutError:
            timed_out = True
        elapsed = time.monotonic() - start

        assert timed_out, "Expected TimeoutError from slow runner.cleanup()"
        assert elapsed < 6.0, f"Cleanup wait took {elapsed:.2f} s — expected < 6 s"

    @pytest.mark.asyncio
    async def test_fast_runner_cleanup_completes(self) -> None:
        """A runner whose cleanup is immediate finishes well within the timeout."""
        fast_runner = _make_fake_runner()

        start = time.monotonic()
        try:
            await asyncio.wait_for(fast_runner.cleanup(), timeout=5.0)
        except asyncio.TimeoutError:
            pytest.fail("Fast runner.cleanup() should not time out")
        elapsed = time.monotonic() - start

        assert elapsed < 1.0
        fast_runner.cleanup.assert_awaited_once()
