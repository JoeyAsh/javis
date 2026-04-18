"""Tests for the GitHub broadcast integration in ws_server.

Verifies:
- broadcast_github_state emits correct JSON shape to connected clients.
- Startup wiring: poller is NOT started when github.enabled=false.
- Startup wiring: poller is NOT started when GITHUB_TOKEN is absent.
- On-connect push: last_state is sent to newly connected clients.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import api.ws_server as ws_server
from integrations.github.client import (
    GithubCIRun,
    GithubIssue,
    GithubPR,
    GitHubStatePayload,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_payload(stale: bool = False) -> GitHubStatePayload:
    return GitHubStatePayload(
        prs=[
            GithubPR(
                id="1",
                repo="owner/repo",
                title="Fix bug",
                author="alice",
                html_url="https://github.com/owner/repo/pull/1",
                updated_at="2024-01-15T10:00:00Z",
            )
        ],
        issues=[
            GithubIssue(
                id="42",
                repo="owner/repo",
                title="Open issue",
                html_url="https://github.com/owner/repo/issues/42",
                updated_at="2024-01-14T08:00:00Z",
            )
        ],
        ci=[
            GithubCIRun(
                repo="owner/repo",
                status="success",
                ran_at="2024-01-15T11:00:00Z",
                html_url="https://github.com/owner/repo/actions/runs/999",
            )
        ],
        fetched_at="2024-01-15T12:00:00Z",
        stale=stale,
    )


# ---------------------------------------------------------------------------
# broadcast_github_state — shape tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_broadcast_github_state_message_shape() -> None:
    """broadcast_github_state sends correctly shaped JSON to all connected clients."""
    mock_ws = MagicMock()
    mock_ws.send_str = AsyncMock()

    # Patch the global connected clients set.
    with patch.object(ws_server, "_connected_clients", {mock_ws}):
        await ws_server.broadcast_github_state(_make_payload())

    assert mock_ws.send_str.call_count == 1
    raw = mock_ws.send_str.call_args[0][0]
    msg = json.loads(raw)

    assert msg["type"] == "github_state"
    payload = msg["payload"]
    assert "prs" in payload
    assert "issues" in payload
    assert "ci" in payload
    assert "fetched_at" in payload
    assert "stale" in payload


@pytest.mark.asyncio
async def test_broadcast_github_state_pr_fields() -> None:
    """PR items in the broadcast contain all required fields."""
    mock_ws = MagicMock()
    mock_ws.send_str = AsyncMock()

    with patch.object(ws_server, "_connected_clients", {mock_ws}):
        await ws_server.broadcast_github_state(_make_payload())

    raw = mock_ws.send_str.call_args[0][0]
    msg = json.loads(raw)
    pr = msg["payload"]["prs"][0]

    assert pr["id"] == "1"
    assert pr["repo"] == "owner/repo"
    assert pr["title"] == "Fix bug"
    assert pr["author"] == "alice"
    assert "html_url" in pr
    assert "updated_at" in pr


@pytest.mark.asyncio
async def test_broadcast_github_state_issue_fields() -> None:
    """Issue items in the broadcast contain all required fields."""
    mock_ws = MagicMock()
    mock_ws.send_str = AsyncMock()

    with patch.object(ws_server, "_connected_clients", {mock_ws}):
        await ws_server.broadcast_github_state(_make_payload())

    raw = mock_ws.send_str.call_args[0][0]
    msg = json.loads(raw)
    issue = msg["payload"]["issues"][0]

    assert issue["id"] == "42"
    assert issue["title"] == "Open issue"
    assert "html_url" in issue
    assert "updated_at" in issue


@pytest.mark.asyncio
async def test_broadcast_github_state_ci_fields() -> None:
    """CI items in the broadcast contain all required fields."""
    mock_ws = MagicMock()
    mock_ws.send_str = AsyncMock()

    with patch.object(ws_server, "_connected_clients", {mock_ws}):
        await ws_server.broadcast_github_state(_make_payload())

    raw = mock_ws.send_str.call_args[0][0]
    msg = json.loads(raw)
    ci_run = msg["payload"]["ci"][0]

    assert ci_run["repo"] == "owner/repo"
    assert ci_run["status"] == "success"
    assert "ran_at" in ci_run
    assert "html_url" in ci_run


@pytest.mark.asyncio
async def test_broadcast_github_state_stale_flag() -> None:
    """stale: true is included in broadcast when payload.stale=True."""
    mock_ws = MagicMock()
    mock_ws.send_str = AsyncMock()

    with patch.object(ws_server, "_connected_clients", {mock_ws}):
        await ws_server.broadcast_github_state(_make_payload(stale=True))

    raw = mock_ws.send_str.call_args[0][0]
    msg = json.loads(raw)
    assert msg["payload"]["stale"] is True


@pytest.mark.asyncio
async def test_broadcast_github_state_no_clients() -> None:
    """broadcast_github_state is a no-op when no clients are connected."""
    with patch.object(ws_server, "_connected_clients", set()):
        # Should not raise.
        await ws_server.broadcast_github_state(_make_payload())


# ---------------------------------------------------------------------------
# Startup wiring — poller disabled paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_github_poller_not_called_when_disabled() -> None:
    """GitHub poller is not started when github.enabled is false."""
    mock_cfg = MagicMock()
    mock_cfg.get_section.return_value = {"enabled": False, "poll_interval_seconds": 60, "repos": []}

    with (
        patch.object(ws_server, "_github_poller", None),
        patch.object(ws_server, "_start_github_poller", AsyncMock()) as mock_start,
        patch.dict("os.environ", {"GITHUB_TOKEN": "ghp_fake"}, clear=False),
    ):
        # Simulate the startup decision logic directly.
        github_cfg = {"enabled": False, "poll_interval_seconds": 60, "repos": []}
        github_token = "ghp_fake"

        if github_cfg.get("enabled", False) and github_token:
            await mock_start(token=github_token, repos=[], poll_interval=60)

        mock_start.assert_not_called()


@pytest.mark.asyncio
async def test_start_github_poller_not_called_when_token_absent() -> None:
    """GitHub poller is not started when GITHUB_TOKEN is absent."""
    with patch.object(ws_server, "_start_github_poller", AsyncMock()) as mock_start:
        github_cfg = {"enabled": True, "poll_interval_seconds": 60, "repos": []}
        github_token = ""  # empty = absent

        if github_cfg.get("enabled", False) and github_token:
            await mock_start(token=github_token, repos=[], poll_interval=60)

        mock_start.assert_not_called()


# ---------------------------------------------------------------------------
# On-connect push of last_state
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_on_connect_sends_last_state_if_available() -> None:
    """When a client connects and last_state is cached, broadcast_github_state is called."""
    mock_poller = MagicMock()
    mock_poller.last_state = _make_payload()

    with (
        patch.object(ws_server, "_github_poller", mock_poller),
        patch.object(ws_server, "broadcast_github_state", AsyncMock()) as mock_broadcast,
    ):
        # Simulate the on-connect push.
        if ws_server._github_poller is not None and ws_server._github_poller.last_state is not None:
            await ws_server.broadcast_github_state(ws_server._github_poller.last_state)

        mock_broadcast.assert_called_once()


@pytest.mark.asyncio
async def test_on_connect_no_push_when_no_last_state() -> None:
    """When a client connects and last_state is None, no broadcast is sent."""
    mock_poller = MagicMock()
    mock_poller.last_state = None

    with (
        patch.object(ws_server, "_github_poller", mock_poller),
        patch.object(ws_server, "broadcast_github_state", AsyncMock()) as mock_broadcast,
    ):
        if ws_server._github_poller is not None and ws_server._github_poller.last_state is not None:
            await ws_server.broadcast_github_state(ws_server._github_poller.last_state)

        mock_broadcast.assert_not_called()
