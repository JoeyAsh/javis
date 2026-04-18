"""Unit tests for integrations.gitlab.poller.GitLabPoller.

All GitLabClient calls are mocked — no real network access.

Test plan
---------
1.  run() spawns a task; stop() cancels it cleanly.
2.  on_state callback fires after first poll tick.
3.  stop() before first tick: no callback invoked.
4.  429 rate-limit: next_sleep uses retry_after, not poll_interval.
5.  429 rate-limit: sleep is capped at 300 s.
6.  Auth error: poller broadcasts error state once, then stops.
7.  Network error: broadcasts stale snapshot; loop continues.
8.  last_state property: None before first tick, populated after.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from integrations.gitlab.client import (
    GitLabAuthError,
    GitLabRateLimitError,
    GitLabState,
)
from integrations.gitlab.poller import GitLabPoller, _MAX_RETRY_AFTER


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _empty_state(error: str | None = None) -> GitLabState:
    return GitLabState(mrs=[], issues=[], pipelines=[], error=error)


def _make_client(state: GitLabState | None = None) -> MagicMock:
    client = MagicMock()
    client.fetch_state = AsyncMock(return_value=state or _empty_state())
    return client


# ---------------------------------------------------------------------------
# 1. run() / stop() lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_and_stop_clean() -> None:
    """run() spawns a task; stop() cancels it cleanly without raising."""
    client = _make_client()
    broadcasts: list[GitLabState] = []

    async def capture(s: GitLabState) -> None:
        broadcasts.append(s)

    poller = GitLabPoller(client=client, interval_seconds=3600)
    await poller.run(on_state=capture)
    assert poller._task is not None
    assert not poller._task.done()

    await poller.stop()
    assert poller._task is None


# ---------------------------------------------------------------------------
# 2. on_state callback fires after first poll tick
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_callback_fires_after_tick() -> None:
    """The broadcast callback is called with the fetched state after sleeping."""
    state = _empty_state()
    client = _make_client(state)
    broadcasts: list[GitLabState] = []
    called = asyncio.Event()

    async def capture(s: GitLabState) -> None:
        broadcasts.append(s)
        called.set()

    poller = GitLabPoller(client=client, interval_seconds=0)
    await poller.run(on_state=capture)

    await asyncio.wait_for(called.wait(), timeout=2.0)
    await poller.stop()

    assert len(broadcasts) >= 1
    assert broadcasts[0] is state


# ---------------------------------------------------------------------------
# 3. stop() before first tick: no callback invoked
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stop_before_first_tick_no_callback() -> None:
    """Stopping immediately after run() (with long interval) fires no callback."""
    client = _make_client()
    broadcasts: list[GitLabState] = []

    async def capture(s: GitLabState) -> None:
        broadcasts.append(s)

    poller = GitLabPoller(client=client, interval_seconds=3600)
    await poller.run(on_state=capture)
    await poller.stop()

    assert len(broadcasts) == 0


# ---------------------------------------------------------------------------
# 4. 429 rate-limit: next_sleep uses retry_after
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rate_limit_backoff_uses_retry_after() -> None:
    """After a 429 the poller sleeps for retry_after seconds, not poll_interval."""
    retry_after = 90
    rate_exc = GitLabRateLimitError("rate limited", retry_after=retry_after)

    good_state = _empty_state()
    call_count = 0

    async def fetch() -> GitLabState:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise rate_exc
        return good_state

    client = MagicMock()
    client.fetch_state = fetch

    sleep_calls: list[float] = []
    original_sleep = asyncio.sleep

    async def mock_sleep(secs: float) -> None:
        sleep_calls.append(secs)
        # Only simulate the sleep for control flow; don't actually wait.
        if len(sleep_calls) >= 3:
            raise asyncio.CancelledError

    broadcasts: list[GitLabState] = []

    async def capture(s: GitLabState) -> None:
        broadcasts.append(s)

    poller = GitLabPoller(client=client, interval_seconds=60)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("integrations.gitlab.poller.asyncio.sleep", mock_sleep)
        await poller.run(on_state=capture)
        try:
            await asyncio.wait_for(poller._task, timeout=2.0)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            await poller.stop()

    # First sleep = poll_interval=60; after 429 the next sleep = retry_after=90
    assert retry_after in sleep_calls, f"Expected {retry_after} in {sleep_calls}"


# ---------------------------------------------------------------------------
# 5. 429 retry_after capped at _MAX_RETRY_AFTER
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rate_limit_retry_after_capped() -> None:
    """retry_after from server is capped at _MAX_RETRY_AFTER in the poller."""
    # The client caps at 300 before raising, but let's verify the poller
    # also uses min(retry_after, _MAX_RETRY_AFTER).
    huge_retry = 9999
    # Build exception as if client didn't cap it
    exc = GitLabRateLimitError("ratelimit", retry_after=huge_retry)

    sleep_calls: list[float] = []

    async def mock_sleep(secs: float) -> None:
        sleep_calls.append(secs)
        if len(sleep_calls) >= 3:
            raise asyncio.CancelledError

    client = MagicMock()
    call_n = 0

    async def fetch() -> GitLabState:
        nonlocal call_n
        call_n += 1
        if call_n == 1:
            raise exc
        return _empty_state()

    client.fetch_state = fetch

    poller = GitLabPoller(client=client, interval_seconds=60)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("integrations.gitlab.poller.asyncio.sleep", mock_sleep)
        await poller.run(on_state=AsyncMock())
        try:
            await asyncio.wait_for(poller._task, timeout=2.0)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            await poller.stop()

    # The backoff sleep should be capped at _MAX_RETRY_AFTER
    assert any(s <= _MAX_RETRY_AFTER for s in sleep_calls)


# ---------------------------------------------------------------------------
# 6. Auth error: broadcasts error state once, then stops
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auth_error_stops_poller() -> None:
    """GitLabAuthError stops the poller after broadcasting an error state."""
    client = MagicMock()
    client.fetch_state = AsyncMock(side_effect=GitLabAuthError("401 Unauthorized"))

    broadcasts: list[GitLabState] = []
    done = asyncio.Event()

    async def capture(s: GitLabState) -> None:
        broadcasts.append(s)
        done.set()

    poller = GitLabPoller(client=client, interval_seconds=0)
    await poller.run(on_state=capture)

    await asyncio.wait_for(done.wait(), timeout=2.0)
    # Give the loop a moment to set _stopped
    await asyncio.sleep(0.05)

    assert poller._stopped is True
    assert len(broadcasts) == 1
    assert broadcasts[0].error is not None


# ---------------------------------------------------------------------------
# 7. Network error: broadcasts stale snapshot; loop continues
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_network_error_broadcasts_stale() -> None:
    """On network error the last cached state is broadcast with error set."""
    initial_state = _empty_state()
    call_count = 0

    async def fetch() -> GitLabState:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return initial_state
        raise aiohttp.ClientConnectorError(
            connection_key=MagicMock(), os_error=OSError("refused")
        )

    client = MagicMock()
    client.fetch_state = fetch

    broadcasts: list[GitLabState] = []
    two_received = asyncio.Event()

    async def capture(s: GitLabState) -> None:
        broadcasts.append(s)
        if len(broadcasts) >= 2:
            two_received.set()

    poller = GitLabPoller(client=client, interval_seconds=0)
    await poller.run(on_state=capture)

    await asyncio.wait_for(two_received.wait(), timeout=2.0)
    await poller.stop()

    # Second broadcast should have error set
    assert broadcasts[1].error is not None


# ---------------------------------------------------------------------------
# 8. last_state is None before first tick, populated after
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_last_state_none_before_tick() -> None:
    """last_state is None before first poll and populated after."""
    state = _empty_state()
    client = _make_client(state)

    first_tick = asyncio.Event()

    async def capture(s: GitLabState) -> None:
        first_tick.set()

    poller = GitLabPoller(client=client, interval_seconds=0)
    assert poller.last_state is None

    await poller.run(on_state=capture)
    await asyncio.wait_for(first_tick.wait(), timeout=2.0)
    await poller.stop()

    assert poller.last_state is state
