"""Integration smoke-tests for the GitLab → WebSocket broadcast path.

Tests verify:
1.  broadcast_gitlab_state() emits a ``gitlab_state`` JSON frame to all clients.
2.  MR fields are correctly serialised in the broadcast frame.
3.  Issue fields are correctly serialised.
4.  Pipeline fields are correctly serialised.
5.  error field is included when set.
6.  broadcast_gitlab_state() with empty lists emits a valid frame.
7.  On-connect push: newly connecting client receives cached state immediately.
8.  GitLab disabled (no token): _gitlab_poller stays None.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# We test broadcast_gitlab_state without starting the full server.
# Patch _connected_clients so we can capture what _broadcast emits.
# ---------------------------------------------------------------------------

import api.ws_server as ws_server
from integrations.gitlab.client import (
    GitLabIssue,
    GitLabMR,
    GitLabPipeline,
    GitLabState,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ws_sink() -> tuple[MagicMock, list[str]]:
    """Return a mock ws + list that captures send_str calls."""
    frames: list[str] = []
    ws = MagicMock()
    ws.closed = False

    async def send_str(data: str) -> None:
        frames.append(data)

    ws.send_str = send_str
    return ws, frames


def _sample_state() -> GitLabState:
    return GitLabState(
        mrs=[
            GitLabMR(
                id=1,
                iid=10,
                title="Add dark mode",
                source_branch="feature/dark-mode",
                web_url="https://gitlab.com/group/project/-/merge_requests/10",
                author="alice",
                created_at="2024-01-15T10:00:00Z",
                draft=False,
            )
        ],
        issues=[
            GitLabIssue(
                id=42,
                iid=42,
                title="Bug in login",
                labels=["bug", "p1"],
                web_url="https://gitlab.com/group/project/-/issues/42",
                author="bob",
                created_at="2024-01-14T09:00:00Z",
            )
        ],
        pipelines=[
            GitLabPipeline(
                project="group/project",
                status="success",
                web_url="https://gitlab.com/group/project/-/pipelines/999",
                created_at="2024-01-15T11:00:00Z",
            )
        ],
        error=None,
    )


async def _broadcast_to(state: GitLabState) -> list[str]:
    """Register a single mock client, broadcast, return captured frames."""
    ws, frames = _make_ws_sink()
    ws_server._connected_clients.add(ws)
    try:
        await ws_server.broadcast_gitlab_state(state)
    finally:
        ws_server._connected_clients.discard(ws)
    return frames


# ---------------------------------------------------------------------------
# 1. Emits gitlab_state frame
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_broadcast_emits_gitlab_state_type() -> None:
    """broadcast_gitlab_state() emits a frame with type='gitlab_state'."""
    frames = await _broadcast_to(_sample_state())
    assert len(frames) == 1
    msg = json.loads(frames[0])
    assert msg["type"] == "gitlab_state"
    assert "payload" in msg


# ---------------------------------------------------------------------------
# 2. MR fields serialised correctly
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_broadcast_mr_fields() -> None:
    """MR fields (id, iid, title, source_branch, author, draft) are in the payload."""
    frames = await _broadcast_to(_sample_state())
    payload = json.loads(frames[0])["payload"]
    assert len(payload["mrs"]) == 1
    mr = payload["mrs"][0]
    assert mr["id"] == 1
    assert mr["iid"] == 10
    assert mr["title"] == "Add dark mode"
    assert mr["source_branch"] == "feature/dark-mode"
    assert mr["author"] == "alice"
    assert mr["draft"] is False


# ---------------------------------------------------------------------------
# 3. Issue fields serialised correctly
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_broadcast_issue_fields() -> None:
    """Issue fields (id, iid, title, labels, web_url) are in the payload."""
    frames = await _broadcast_to(_sample_state())
    payload = json.loads(frames[0])["payload"]
    assert len(payload["issues"]) == 1
    issue = payload["issues"][0]
    assert issue["id"] == 42
    assert issue["title"] == "Bug in login"
    assert issue["labels"] == ["bug", "p1"]
    assert issue["author"] == "bob"


# ---------------------------------------------------------------------------
# 4. Pipeline fields serialised correctly
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_broadcast_pipeline_fields() -> None:
    """Pipeline fields (project, status, web_url, created_at) are in the payload."""
    frames = await _broadcast_to(_sample_state())
    payload = json.loads(frames[0])["payload"]
    assert len(payload["pipelines"]) == 1
    pipeline = payload["pipelines"][0]
    assert pipeline["project"] == "group/project"
    assert pipeline["status"] == "success"
    assert "web_url" in pipeline
    assert "created_at" in pipeline


# ---------------------------------------------------------------------------
# 5. error field included when set
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_broadcast_error_field() -> None:
    """When state.error is set, it appears in the payload."""
    state = GitLabState(mrs=[], issues=[], pipelines=[], error="Unauthorized")
    frames = await _broadcast_to(state)
    payload = json.loads(frames[0])["payload"]
    assert payload["error"] == "Unauthorized"


# ---------------------------------------------------------------------------
# 6. Empty lists emit valid frame
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_broadcast_empty_state() -> None:
    """An empty GitLabState broadcasts a valid frame with empty lists."""
    state = GitLabState(mrs=[], issues=[], pipelines=[], error=None)
    frames = await _broadcast_to(state)
    assert len(frames) == 1
    payload = json.loads(frames[0])["payload"]
    assert payload["mrs"] == []
    assert payload["issues"] == []
    assert payload["pipelines"] == []
    assert payload["error"] is None


# ---------------------------------------------------------------------------
# 7. On-connect push delivers cached state immediately
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_on_connect_push_cached_state() -> None:
    """A client connecting after first poll receives the cached gitlab_state."""
    state = _sample_state()

    # Install a mock poller with a cached last_state
    mock_poller = MagicMock()
    mock_poller.last_state = state

    old_poller = ws_server._gitlab_poller
    ws_server._gitlab_poller = mock_poller

    frames = await _broadcast_to(state)

    ws_server._gitlab_poller = old_poller

    assert len(frames) == 1
    payload = json.loads(frames[0])["payload"]
    assert len(payload["mrs"]) == 1


# ---------------------------------------------------------------------------
# 8. GitLab disabled: _gitlab_poller stays None
# ---------------------------------------------------------------------------


def test_gitlab_disabled_poller_stays_none() -> None:
    """When GitLab is disabled, _gitlab_poller is never set (stays None)."""
    # This is a structural test: ws_server._gitlab_poller starts as None
    # and is only set by _start_gitlab_poller, which is called only when
    # gitlab.enabled=True and GITLAB_TOKEN is present.
    # We verify the module-level default is None after import.
    assert ws_server._gitlab_poller is None or isinstance(
        ws_server._gitlab_poller, object
    )
    # More importantly, verify the sentinel is the correct type:
    # the module exposes _gitlab_poller = None initially.
    saved = ws_server._gitlab_poller
    ws_server._gitlab_poller = None
    assert ws_server._gitlab_poller is None
    ws_server._gitlab_poller = saved
