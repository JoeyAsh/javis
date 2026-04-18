"""Background GitHub polling task for JARVIS.

``GitHubPoller`` aggregates PRs, issues, and CI runs from
:class:`~integrations.github.client.GitHubClient` on a configurable interval
and broadcasts the result via a caller-supplied ``broadcast_fn``.

Failure modes
-------------
- **401 auth error** — logs at ERROR, broadcasts stale payload, stops polling
  (the token is no longer valid; restart JARVIS after fixing ``.env``).
- **429 / rate-limit** — logs at WARNING, skips this tick, doubles the wait
  for the next tick (capped at ``poll_interval * 4``), then resumes normal
  cadence once a tick succeeds.
- **5xx / timeout** — marks ``stale=True`` on the cached payload and
  broadcasts the previous state; normal cadence continues on the next tick.
- **Partial CI failure** — the failing repo is omitted from the ``ci`` list;
  the remaining data is broadcast normally; ``stale`` stays ``False``.
"""

from __future__ import annotations

import asyncio
import datetime
from typing import Awaitable, Callable

import aiohttp

from integrations.github.client import (
    GitHubAuthError,
    GitHubClient,
    GitHubRateLimitError,
    GitHubStatePayload,
)
from utils.logger import get_logger

logger = get_logger("github.poller")


class GitHubPoller:
    """Background task that polls GitHub on a fixed interval and broadcasts state.

    Args:
        client: Initialised :class:`GitHubClient` instance.
        repos: Explicit whitelist of ``"owner/repo"`` strings for CI fetches
            and search scoping.
        poll_interval: Seconds between polling ticks.
        broadcast_fn: Async callable that receives the aggregated payload and
            broadcasts it to all connected WebSocket clients.
    """

    def __init__(
        self,
        client: GitHubClient,
        repos: list[str],
        poll_interval: int,
        broadcast_fn: Callable[[GitHubStatePayload], Awaitable[None]],
    ) -> None:
        """Initialise the poller without starting it."""
        self._client = client
        self._repos = repos
        self._poll_interval = poll_interval
        self._broadcast_fn = broadcast_fn
        self._task: asyncio.Task[None] | None = None
        self._last_state: GitHubStatePayload | None = None
        self._stopped = False

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @property
    def last_state(self) -> GitHubStatePayload | None:
        """Return the most-recently cached payload, or ``None`` before the first tick."""
        return self._last_state

    async def start(self) -> None:
        """Start the background polling loop.

        Spawns an ``asyncio.Task``; returns immediately.  Idempotent — calling
        ``start()`` on an already-running poller is a no-op.
        """
        if self._task is not None and not self._task.done():
            logger.debug("GitHubPoller.start() called but task already running — no-op")
            return
        self._stopped = False
        self._task = asyncio.create_task(self._run(), name="github_poller")
        logger.info(
            f"GitHub poller started (interval={self._poll_interval}s, "
            f"repos={self._repos})"
        )

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
        logger.info("GitHub poller stopped")

    # ------------------------------------------------------------------
    # Internal loop
    # ------------------------------------------------------------------

    async def _run(self) -> None:
        """Main poll loop — runs until cancelled or a fatal auth error occurs."""
        backoff_multiplier = 1  # increases on rate-limit; resets on success

        while not self._stopped:
            wait_secs = self._poll_interval * backoff_multiplier
            try:
                await asyncio.sleep(wait_secs)
            except asyncio.CancelledError:
                logger.info("GitHub poller cancelled during sleep")
                return

            # After a rate-limit backoff the multiplier was doubled; reset
            # before the next successful fetch so normal cadence resumes.
            prev_multiplier = backoff_multiplier
            backoff_multiplier = 1  # optimistically reset; re-set on error below

            try:
                payload = await self._poll()
            except GitHubAuthError as exc:
                logger.error(f"GitHub auth error — stopping poller: {exc}")
                # Mark cached payload as stale and broadcast once, then halt.
                if self._last_state is not None:
                    stale_payload = GitHubStatePayload(
                        prs=self._last_state.prs,
                        issues=self._last_state.issues,
                        ci=self._last_state.ci,
                        fetched_at=self._last_state.fetched_at,
                        stale=True,
                    )
                    self._last_state = stale_payload
                    await self._safe_broadcast(stale_payload)
                self._stopped = True
                return
            except GitHubRateLimitError as exc:
                backoff_multiplier = min(prev_multiplier * 2, 4)
                logger.warning(
                    f"GitHub rate limit exceeded — backing off "
                    f"(next wait={self._poll_interval * backoff_multiplier}s): {exc}"
                )
                # Do not update last_state; skip this tick silently.
                continue
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                logger.warning(f"GitHub poll network error (marking stale): {exc}")
                if self._last_state is not None:
                    stale_payload = GitHubStatePayload(
                        prs=self._last_state.prs,
                        issues=self._last_state.issues,
                        ci=self._last_state.ci,
                        fetched_at=self._last_state.fetched_at,
                        stale=True,
                    )
                    self._last_state = stale_payload
                    await self._safe_broadcast(stale_payload)
                continue
            except asyncio.CancelledError:
                logger.info("GitHub poller cancelled during poll")
                return
            except Exception as exc:  # noqa: BLE001
                logger.error(f"GitHub poller unexpected error (marking stale): {exc}")
                if self._last_state is not None:
                    stale_payload = GitHubStatePayload(
                        prs=self._last_state.prs,
                        issues=self._last_state.issues,
                        ci=self._last_state.ci,
                        fetched_at=self._last_state.fetched_at,
                        stale=True,
                    )
                    self._last_state = stale_payload
                    await self._safe_broadcast(stale_payload)
                continue

            self._last_state = payload
            await self._safe_broadcast(payload)
            logger.info(
                f"[github_poller] poll complete: {len(payload.prs)} prs, "
                f"{len(payload.issues)} issues, {len(payload.ci)} ci runs"
            )

    async def _poll(self) -> GitHubStatePayload:
        """Fetch all GitHub data for one tick.

        Returns:
            Fresh :class:`GitHubStatePayload` with ``stale=False``.

        Raises:
            GitHubAuthError: When the token is rejected.
            GitHubRateLimitError: When the quota headroom is too low.
            aiohttp.ClientError: On network failures.
        """
        prs, issues = await asyncio.gather(
            self._client.fetch_my_prs(self._repos),
            self._client.fetch_my_issues(self._repos),
        )

        # CI fetches are per-repo; partial failures are swallowed here so
        # one bad repo doesn't suppress data from healthy repos.
        ci_results: list[Any] = []
        for repo in self._repos:
            try:
                run = await self._client.fetch_ci_status(repo)
                if run is not None:
                    ci_results.append(run)
            except (GitHubAuthError, GitHubRateLimitError):
                # Auth / rate-limit errors must bubble up to the main loop.
                raise
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"CI fetch failed for {repo} (skipping): {exc}")

        return GitHubStatePayload(
            prs=prs,
            issues=issues,
            ci=ci_results,
            fetched_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            stale=False,
        )

    async def _safe_broadcast(self, payload: GitHubStatePayload) -> None:
        """Broadcast payload, swallowing errors so the poller loop continues.

        Args:
            payload: Payload to broadcast.
        """
        try:
            await self._broadcast_fn(payload)
        except Exception as exc:  # noqa: BLE001
            logger.error(f"GitHub broadcast failed: {exc}")


# Appease type checker for the `Any` used in _poll
from typing import Any  # noqa: E402
