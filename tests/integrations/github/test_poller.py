"""Unit tests for integrations.github.poller.GitHubPoller.

All GitHubClient calls are mocked — no real network access.
"""

from __future__ import annotations

import asyncio
import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from integrations.github.client import (
    GitHubAuthError,
    GitHubRateLimitError,
    GithubCIRun,
    GithubIssue,
    GithubPR,
    GitHubStatePayload,
)
from integrations.github.poller import GitHubPoller


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client(
    prs: list[GithubPR] | None = None,
    issues: list[GithubIssue] | None = None,
    ci: list[GithubCIRun] | None = None,
) -> MagicMock:
    """Return a mock GitHubClient with configurable return values."""
    client = MagicMock()
    client.fetch_my_prs = AsyncMock(return_value=prs or [])
    client.fetch_my_issues = AsyncMock(return_value=issues or [])
    client.fetch_ci_status = AsyncMock(return_value=(ci[0] if ci else None))
    return client


def _sample_pr() -> GithubPR:
    return GithubPR(
        id="1",
        repo="owner/repo",
        title="Fix bug",
        author="alice",
        html_url="https://github.com/owner/repo/pull/1",
        updated_at="2024-01-15T10:00:00Z",
    )


def _sample_ci() -> GithubCIRun:
    return GithubCIRun(
        repo="owner/repo",
        status="success",
        ran_at="2024-01-15T11:00:00Z",
        html_url="https://github.com/owner/repo/actions/runs/999",
    )


# ---------------------------------------------------------------------------
# start / stop lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_and_stop_clean() -> None:
    """start() spawns a task; stop() cancels it cleanly."""
    client = _make_client()
    broadcasts: list[GitHubStatePayload] = []

    async def capture(payload: GitHubStatePayload) -> None:
        broadcasts.append(payload)

    poller = GitHubPoller(
        client=client,
        repos=["owner/repo"],
        poll_interval=3600,  # very long — won't fire in test
        broadcast_fn=capture,
    )

    await poller.start()
    assert poller._task is not None
    assert not poller._task.done()

    await poller.stop()
    assert poller._task is None


@pytest.mark.asyncio
async def test_start_idempotent() -> None:
    """Calling start() twice does not create a second task."""
    client = _make_client()
    poller = GitHubPoller(
        client=client,
        repos=[],
        poll_interval=3600,
        broadcast_fn=AsyncMock(),
    )
    await poller.start()
    task1 = poller._task
    await poller.start()  # second call — should be a no-op
    task2 = poller._task

    assert task1 is task2
    await poller.stop()


# ---------------------------------------------------------------------------
# Broadcast on first tick
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_first_tick_broadcasts_payload() -> None:
    """After one poll interval the poller broadcasts aggregated state."""
    pr = _sample_pr()
    ci = _sample_ci()
    client = _make_client(prs=[pr], ci=[ci])

    received: list[GitHubStatePayload] = []

    async def capture(payload: GitHubStatePayload) -> None:
        received.append(payload)

    poller = GitHubPoller(
        client=client,
        repos=["owner/repo"],
        poll_interval=0,  # instant
        broadcast_fn=capture,
    )
    await poller.start()
    # Give the event loop a moment to execute the poll task.
    await asyncio.sleep(0.05)
    await poller.stop()

    assert len(received) >= 1
    payload = received[0]
    assert payload.stale is False
    assert len(payload.prs) == 1
    assert payload.prs[0].id == "1"
    assert len(payload.ci) == 1
    assert payload.ci[0].status == "success"


# ---------------------------------------------------------------------------
# last_state property
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_last_state_none_before_first_tick() -> None:
    """last_state is None before the first successful poll."""
    client = _make_client()
    poller = GitHubPoller(
        client=client,
        repos=[],
        poll_interval=3600,
        broadcast_fn=AsyncMock(),
    )
    assert poller.last_state is None
    await poller.start()
    assert poller.last_state is None  # still None — poll hasn't fired
    await poller.stop()


@pytest.mark.asyncio
async def test_last_state_populated_after_tick() -> None:
    """last_state is set after the first successful poll."""
    pr = _sample_pr()
    client = _make_client(prs=[pr])
    poller = GitHubPoller(
        client=client,
        repos=[],
        poll_interval=0,
        broadcast_fn=AsyncMock(),
    )
    await poller.start()
    await asyncio.sleep(0.05)
    await poller.stop()

    assert poller.last_state is not None
    assert len(poller.last_state.prs) == 1


# ---------------------------------------------------------------------------
# Auth error — poller halts, marks stale
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auth_error_stops_poller_and_marks_stale() -> None:
    """A 401 auth error stops the poller and sets stale=True on the cached payload."""
    # Seed last_state with a valid payload, then make the next fetch fail.
    client = _make_client()
    client.fetch_my_prs = AsyncMock(side_effect=GitHubAuthError("401"))

    received: list[GitHubStatePayload] = []

    async def capture(payload: GitHubStatePayload) -> None:
        received.append(payload)

    poller = GitHubPoller(
        client=client,
        repos=[],
        poll_interval=0,
        broadcast_fn=capture,
    )
    # Plant a fake last_state so we can verify stale=True is set on broadcast.
    poller._last_state = GitHubStatePayload(
        prs=[_sample_pr()],
        issues=[],
        ci=[],
        fetched_at="2024-01-15T00:00:00Z",
        stale=False,
    )

    await poller.start()
    # Give event loop time to fire the poll and hit the auth error.
    await asyncio.sleep(0.1)

    # Poller should have stopped itself.
    assert poller._stopped is True

    # The broadcast should have emitted a stale payload.
    stale_broadcasts = [p for p in received if p.stale]
    assert len(stale_broadcasts) >= 1


# ---------------------------------------------------------------------------
# Rate-limit error — skip tick, double backoff
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rate_limit_skips_tick_no_crash() -> None:
    """A rate-limit error causes the poller to skip the tick without crashing."""
    call_count = 0

    async def failing_prs(*_: Any, **__: Any) -> list[GithubPR]:
        nonlocal call_count
        call_count += 1
        raise GitHubRateLimitError("429")

    client = _make_client()
    client.fetch_my_prs = failing_prs

    poller = GitHubPoller(
        client=client,
        repos=[],
        poll_interval=0,
        broadcast_fn=AsyncMock(),
    )
    await poller.start()
    await asyncio.sleep(0.05)
    await poller.stop()

    # Poller survived — no crash.
    assert call_count >= 1
    # last_state remains None (no successful tick).
    assert poller.last_state is None


# ---------------------------------------------------------------------------
# Partial CI failure — other data still broadcast
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_partial_ci_failure_does_not_set_stale() -> None:
    """When one repo's CI fetch fails, others succeed and stale stays False."""
    pr = _sample_pr()
    client = _make_client(prs=[pr])

    async def flaky_ci(repo: str) -> GithubCIRun | None:
        if repo == "bad/repo":
            raise RuntimeError("CI API down")
        return _sample_ci()

    client.fetch_ci_status = flaky_ci

    received: list[GitHubStatePayload] = []

    async def capture(payload: GitHubStatePayload) -> None:
        received.append(payload)

    poller = GitHubPoller(
        client=client,
        repos=["good/repo", "bad/repo"],
        poll_interval=0,
        broadcast_fn=capture,
    )
    await poller.start()
    await asyncio.sleep(0.05)
    await poller.stop()

    assert len(received) >= 1
    payload = received[0]
    assert payload.stale is False
    # Only the good repo's CI run should be present.
    assert len(payload.ci) == 1
    assert payload.ci[0].repo == "owner/repo"


# ---------------------------------------------------------------------------
# Network error — stale flag set, last state broadcast
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_network_error_marks_stale_and_broadcasts_last_state() -> None:
    """On network error, the poller marks stale=True and broadcasts cached state."""
    import aiohttp

    client = _make_client()
    client.fetch_my_prs = AsyncMock(side_effect=aiohttp.ClientConnectionError("timeout"))

    received: list[GitHubStatePayload] = []

    async def capture(payload: GitHubStatePayload) -> None:
        received.append(payload)

    poller = GitHubPoller(
        client=client,
        repos=[],
        poll_interval=0,
        broadcast_fn=capture,
    )
    # Pre-seed last_state.
    poller._last_state = GitHubStatePayload(
        prs=[_sample_pr()],
        issues=[],
        ci=[],
        fetched_at="2024-01-15T00:00:00Z",
        stale=False,
    )

    await poller.start()
    await asyncio.sleep(0.05)
    await poller.stop()

    stale_payloads = [p for p in received if p.stale]
    assert len(stale_payloads) >= 1


# ---------------------------------------------------------------------------
# Empty repos list — CI is empty, PRs + issues still fetched
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_repos_list() -> None:
    """With repos=[], the CI list is empty but PRs and issues are still fetched."""
    pr = _sample_pr()
    client = _make_client(prs=[pr])

    received: list[GitHubStatePayload] = []

    async def capture(payload: GitHubStatePayload) -> None:
        received.append(payload)

    poller = GitHubPoller(
        client=client,
        repos=[],
        poll_interval=0,
        broadcast_fn=capture,
    )
    await poller.start()
    await asyncio.sleep(0.05)
    await poller.stop()

    assert len(received) >= 1
    assert received[0].ci == []
    assert len(received[0].prs) == 1
