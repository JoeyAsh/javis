"""Background GitLab polling task for JARVIS.

``GitLabPoller`` calls :class:`~integrations.gitlab.client.GitLabClient.fetch_state`
on a configurable interval and pushes the result to all connected WebSocket
clients via a caller-supplied async callback.

Failure modes
-------------
- **401 auth error** — logs at ERROR, broadcasts the error payload once, stops
  the poller.  The token is invalid; restart JARVIS after fixing ``.env``.
- **429 rate-limit** — reads ``GitLabRateLimitError.retry_after``; backs off
  by that duration (capped at 300 s) instead of the normal interval, then
  resumes once a tick succeeds.
- **Network / timeout errors** — logs at WARNING; broadcasts last cached
  snapshot (if any) unchanged; poller continues at the next normal tick.
- **Partial failures** — ``GitLabState.error`` is set to the first error
  message; already-fetched data is still broadcast so the panel is never
  entirely blank.
"""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

import aiohttp

from integrations.gitlab.client import (
    GitLabAuthError,
    GitLabClient,
    GitLabRateLimitError,
    GitLabState,
)
from utils.logger import get_logger

logger = get_logger("gitlab.poller")

_MAX_RETRY_AFTER = 300  # cap for Retry-After back-off in seconds


class GitLabPoller:
    """Background task that polls GitLab on a fixed interval and broadcasts state.

    Args:
        client: Initialised :class:`GitLabClient` instance.
        interval_seconds: Seconds between polling ticks.
    """

    def __init__(self, client: GitLabClient, interval_seconds: int) -> None:
        """Initialise the poller without starting it."""
        self._client = client
        self._interval = interval_seconds
        self._task: asyncio.Task[None] | None = None
        self._last_state: GitLabState | None = None
        self._stopped = False

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @property
    def last_state(self) -> GitLabState | None:
        """Return the most-recently cached payload, or ``None`` before the first tick."""
        return self._last_state

    async def run(
        self,
        on_state: Callable[[GitLabState], Awaitable[None]],
    ) -> None:
        """Start the background polling loop.

        Spawns an ``asyncio.Task``; returns immediately.  Idempotent — calling
        ``run()`` while already running is a no-op.

        Args:
            on_state: Async callback invoked with the latest :class:`GitLabState`
                after each poll tick.
        """
        if self._task is not None and not self._task.done():
            logger.debug("GitLabPoller.run() called but task already running — no-op")
            return
        self._stopped = False
        self._task = asyncio.create_task(
            self._run_loop(on_state), name="gitlab_poller"
        )
        logger.info(f"GitLab poller started (interval={self._interval}s)")

    async def stop(self) -> None:
        """Stop the background polling loop and wait for clean shutdown."""
        self._stopped = True
        if self._task is not None and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        self._task = None
        logger.info("GitLab poller stopped")

    # ------------------------------------------------------------------
    # Internal loop
    # ------------------------------------------------------------------

    async def _run_loop(
        self,
        on_state: Callable[[GitLabState], Awaitable[None]],
    ) -> None:
        """Main poll loop — runs until cancelled or a fatal auth error occurs.

        Args:
            on_state: Broadcast callback.
        """
        next_sleep = self._interval

        while not self._stopped:
            try:
                await asyncio.sleep(next_sleep)
            except asyncio.CancelledError:
                logger.info("GitLab poller cancelled during sleep")
                return

            # Optimistically reset sleep to normal interval; override below on error.
            next_sleep = self._interval

            try:
                state = await self._client.fetch_state()
            except GitLabAuthError as exc:
                logger.error(f"GitLab auth error — stopping poller: {exc}")
                # Build an error-flagged payload from last cache (or empty).
                error_state = GitLabState(
                    mrs=self._last_state.mrs if self._last_state else [],
                    issues=self._last_state.issues if self._last_state else [],
                    pipelines=self._last_state.pipelines if self._last_state else [],
                    error=str(exc),
                )
                self._last_state = error_state
                await self._safe_broadcast(on_state, error_state)
                self._stopped = True
                return
            except GitLabRateLimitError as exc:
                next_sleep = min(exc.retry_after, _MAX_RETRY_AFTER)
                logger.warning(
                    f"GitLab rate limit — backing off {next_sleep}s: {exc}"
                )
                # Skip this tick; do not update last_state.
                continue
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                logger.warning(f"GitLab poll network error: {exc}")
                if self._last_state is not None:
                    stale = GitLabState(
                        mrs=self._last_state.mrs,
                        issues=self._last_state.issues,
                        pipelines=self._last_state.pipelines,
                        error=str(exc),
                    )
                    self._last_state = stale
                    await self._safe_broadcast(on_state, stale)
                continue
            except asyncio.CancelledError:
                logger.info("GitLab poller cancelled during fetch")
                return
            except Exception as exc:  # noqa: BLE001
                logger.error(f"GitLab poller unexpected error: {exc}")
                if self._last_state is not None:
                    stale = GitLabState(
                        mrs=self._last_state.mrs,
                        issues=self._last_state.issues,
                        pipelines=self._last_state.pipelines,
                        error=str(exc),
                    )
                    self._last_state = stale
                    await self._safe_broadcast(on_state, stale)
                continue

            self._last_state = state
            await self._safe_broadcast(on_state, state)
            logger.info(
                f"[gitlab_poller] poll complete: {len(state.mrs)} MRs, "
                f"{len(state.issues)} issues, {len(state.pipelines)} pipelines"
                + (f", error={state.error!r}" if state.error else "")
            )

    async def _safe_broadcast(
        self,
        on_state: Callable[[GitLabState], Awaitable[None]],
        state: GitLabState,
    ) -> None:
        """Broadcast state, swallowing errors so the poller loop continues.

        Args:
            on_state: Broadcast callback.
            state: State to broadcast.
        """
        try:
            await on_state(state)
        except Exception as exc:  # noqa: BLE001
            logger.error(f"GitLab broadcast failed: {exc}")
