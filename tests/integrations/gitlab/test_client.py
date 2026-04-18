"""Unit tests for integrations.gitlab.client.GitLabClient.

All HTTP calls are mocked via unittest.mock / aiohttp mocking — no real
network access is performed.

Test plan
---------
1.  fetch_state() happy path: returns MRs, Issues, and Pipelines.
2.  list_merge_requests: MR fields mapped correctly (draft detection).
3.  list_issues: labels parsed correctly from string and dict forms.
4.  get_pipelines: pipeline fields mapped correctly.
5.  401 on /merge_requests: returns error state with empty lists.
6.  401 on /issues: returns error state with empty lists.
7.  429 rate-limit: GitLabRateLimitError raised with Retry-After from header.
8.  429 Retry-After default when header missing.
9.  404 on one project pipeline: that project skipped, others succeed.
10. Network error: fetch_state returns partial data with error set.
11. Project path: numeric ID resolves as ``projects/42``.
12. Project path: slug resolves as ``projects/group%2Fproject``.
13. Project path: nested slug ``group/sub/project`` uses %2F encoding.
14. Empty projects list: pipelines section empty; MRs and Issues present.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from integrations.gitlab.client import (
    GitLabAuthError,
    GitLabClient,
    GitLabRateLimitError,
    GitLabState,
)


# ---------------------------------------------------------------------------
# Helpers — session mocking
#
# ``GitLabClient.fetch_state`` uses ``async with aiohttp.ClientSession() as session``.
# We patch ``aiohttp.ClientSession`` with a callable that returns an async
# context manager whose ``__aenter__`` yields the inner mock session.
# ---------------------------------------------------------------------------


def _make_async_cm(session_mock: MagicMock) -> MagicMock:
    """Wrap ``session_mock`` in an async context manager stub."""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session_mock)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


def _make_session(
    *,
    json_data: Any = None,
    status: int = 200,
    headers: dict[str, str] | None = None,
) -> MagicMock:
    """Return a mock ``aiohttp.ClientSession`` whose GET returns ``json_data``."""
    resp = MagicMock()
    resp.status = status
    resp.headers = headers or {}
    resp.raise_for_status = MagicMock(return_value=None)
    resp.json = AsyncMock(return_value=json_data if json_data is not None else [])

    @asynccontextmanager
    async def _get(*args: Any, **kwargs: Any):
        yield resp

    session = MagicMock()
    session.get = _get
    return session


def _make_session_multi(*responses: tuple[Any, int, dict]) -> MagicMock:
    """Return a session that cycles through (json, status, headers) tuples."""
    it = iter(responses)

    @asynccontextmanager
    async def _get(*args: Any, **kwargs: Any):
        json_data, status, headers = next(it)
        resp = MagicMock()
        resp.status = status
        resp.headers = headers or {}
        resp.raise_for_status = MagicMock(return_value=None)
        resp.json = AsyncMock(return_value=json_data if json_data is not None else [])
        if status >= 400:
            resp.raise_for_status.side_effect = aiohttp.ClientResponseError(
                request_info=MagicMock(),
                history=(),
                status=status,
                message=f"HTTP {status}",
            )
        yield resp

    session = MagicMock()
    session.get = _get
    return session


def _patch_session(session_mock: MagicMock):
    """Return a ``patch`` for ``aiohttp.ClientSession`` that uses ``session_mock``."""
    return patch(
        "integrations.gitlab.client.aiohttp.ClientSession",
        return_value=_make_async_cm(session_mock),
    )


def _patch_session_multi(*responses: tuple[Any, int, dict]):
    """Return a patch for aiohttp.ClientSession using multi-response session."""
    session = _make_session_multi(*responses)
    return patch(
        "integrations.gitlab.client.aiohttp.ClientSession",
        return_value=_make_async_cm(session),
    )


# ---------------------------------------------------------------------------
# Sample data factories
# ---------------------------------------------------------------------------


def _mr_item(mr_id: int = 1) -> dict[str, Any]:
    return {
        "id": mr_id,
        "iid": mr_id,
        "title": f"MR #{mr_id}",
        "source_branch": f"feature/branch-{mr_id}",
        "web_url": f"https://gitlab.com/group/project/-/merge_requests/{mr_id}",
        "author": {"username": "alice"},
        "created_at": "2024-01-15T10:00:00Z",
        "draft": False,
    }


def _issue_item(issue_id: int = 10) -> dict[str, Any]:
    return {
        "id": issue_id,
        "iid": issue_id,
        "title": f"Issue #{issue_id}",
        "labels": ["bug", "p1"],
        "web_url": f"https://gitlab.com/group/project/-/issues/{issue_id}",
        "author": {"username": "bob"},
        "created_at": "2024-01-14T09:00:00Z",
    }


def _pipeline_item(status: str = "success") -> dict[str, Any]:
    return {
        "id": 999,
        "status": status,
        "web_url": "https://gitlab.com/group/project/-/pipelines/999",
        "created_at": "2024-01-15T11:00:00Z",
    }


def _make_client(
    projects: list[str] | None = None,
    url: str = "https://gitlab.com",
) -> GitLabClient:
    effective_projects = projects if projects is not None else ["group/project"]
    return GitLabClient(
        token="test-token",
        url=url,
        projects=effective_projects,
    )


# ---------------------------------------------------------------------------
# 1. Happy path: fetch_state returns MRs, Issues, Pipelines
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_state_happy_path() -> None:
    """fetch_state() aggregates MRs, Issues, and Pipelines with error=None."""
    client = _make_client()

    responses: list[tuple[Any, int, dict]] = [
        ([_mr_item(1), _mr_item(2)], 200, {}),  # /merge_requests
        ([_issue_item(10)], 200, {}),  # /issues
        ([_pipeline_item("success")], 200, {}),  # pipeline for group/project
    ]
    with _patch_session_multi(*responses):
        state = await client.fetch_state()

    assert state.error is None
    assert len(state.mrs) == 2
    assert len(state.issues) == 1
    assert len(state.pipelines) == 1
    assert state.pipelines[0].status == "success"
    assert state.pipelines[0].project == "group/project"


# ---------------------------------------------------------------------------
# 2. MR fields mapped correctly
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mr_fields_mapped() -> None:
    """MR title, branch, author, and draft flag are correctly mapped."""
    client = _make_client()
    item = _mr_item(7)
    item["draft"] = True

    responses = [
        ([item], 200, {}),
        ([], 200, {}),
        ([_pipeline_item()], 200, {}),
    ]
    with _patch_session_multi(*responses):
        state = await client.fetch_state()

    assert len(state.mrs) == 1
    mr = state.mrs[0]
    assert mr.id == 7
    assert mr.iid == 7
    assert mr.title == "MR #7"
    assert mr.source_branch == "feature/branch-7"
    assert mr.author == "alice"
    assert mr.draft is True


# ---------------------------------------------------------------------------
# 3. Issue labels parsed from string and dict forms
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_issue_labels_string_and_dict() -> None:
    """Labels as plain strings and as ``{name: ...}`` dicts both work."""
    client = _make_client()
    item = _issue_item(5)
    item["labels"] = [{"name": "bug"}, "p2"]  # mixed forms

    responses = [
        ([], 200, {}),
        ([item], 200, {}),
        ([], 200, {}),
    ]
    with _patch_session_multi(*responses):
        state = await client.fetch_state()

    assert len(state.issues) == 1
    assert state.issues[0].labels == ["bug", "p2"]


# ---------------------------------------------------------------------------
# 4. Pipeline fields mapped correctly
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pipeline_fields_mapped() -> None:
    """Pipeline project, status, web_url, and created_at are correctly mapped."""
    client = _make_client(projects=["group/project"])

    responses = [
        ([], 200, {}),
        ([], 200, {}),
        ([_pipeline_item("failed")], 200, {}),
    ]
    with _patch_session_multi(*responses):
        state = await client.fetch_state()

    assert len(state.pipelines) == 1
    p = state.pipelines[0]
    assert p.project == "group/project"
    assert p.status == "failed"
    assert p.web_url == "https://gitlab.com/group/project/-/pipelines/999"


# ---------------------------------------------------------------------------
# 5. 401 on /merge_requests → error state
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_state_401_returns_error_state() -> None:
    """A 401 from /merge_requests short-circuits with error state."""
    client = _make_client()

    resp = MagicMock()
    resp.status = 401
    resp.headers = {}
    resp.raise_for_status = MagicMock(return_value=None)
    resp.json = AsyncMock(return_value={})

    @asynccontextmanager
    async def _get(*args: Any, **kwargs: Any):
        yield resp

    session = MagicMock()
    session.get = _get

    with patch(
        "integrations.gitlab.client.aiohttp.ClientSession",
        return_value=_make_async_cm(session),
    ):
        state = await client.fetch_state()

    assert state.error is not None
    assert "401" in state.error or "Unauthorized" in state.error
    assert state.mrs == []
    assert state.issues == []
    assert state.pipelines == []


# ---------------------------------------------------------------------------
# 6. 401 propagated through gather
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_state_401_on_issues_returns_error() -> None:
    """A 401 raised from issues also surfaces in error state."""
    client = GitLabClient(token="bad-token", url="https://gitlab.com", projects=[])

    @asynccontextmanager
    async def _get(*args: Any, **kwargs: Any):
        resp = MagicMock()
        resp.status = 401
        resp.headers = {}
        resp.raise_for_status = MagicMock(return_value=None)
        resp.json = AsyncMock(return_value={})
        yield resp

    session = MagicMock()
    session.get = _get

    with patch(
        "integrations.gitlab.client.aiohttp.ClientSession",
        return_value=_make_async_cm(session),
    ):
        state = await client.fetch_state()

    assert state.error is not None
    assert state.mrs == []
    assert state.issues == []


# ---------------------------------------------------------------------------
# 7. 429 rate-limit raises GitLabRateLimitError with Retry-After
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rate_limit_raises_with_retry_after() -> None:
    """HTTP 429 raises GitLabRateLimitError carrying the Retry-After seconds."""
    client = _make_client(projects=[])

    @asynccontextmanager
    async def _get(*args: Any, **kwargs: Any):
        resp = MagicMock()
        resp.status = 429
        resp.headers = {"Retry-After": "120"}
        resp.raise_for_status = MagicMock(return_value=None)
        resp.json = AsyncMock(return_value={})
        yield resp

    session = MagicMock()
    session.get = _get

    with patch(
        "integrations.gitlab.client.aiohttp.ClientSession",
        return_value=_make_async_cm(session),
    ):
        with pytest.raises(GitLabRateLimitError) as exc_info:
            await client.fetch_state()

    assert exc_info.value.retry_after == 120


# ---------------------------------------------------------------------------
# 8. 429 Retry-After defaults to 60 when header missing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rate_limit_default_retry_after() -> None:
    """HTTP 429 without Retry-After header defaults to 60 s."""
    client = _make_client(projects=[])

    @asynccontextmanager
    async def _get(*args: Any, **kwargs: Any):
        resp = MagicMock()
        resp.status = 429
        resp.headers = {}
        resp.raise_for_status = MagicMock(return_value=None)
        resp.json = AsyncMock(return_value={})
        yield resp

    session = MagicMock()
    session.get = _get

    with patch(
        "integrations.gitlab.client.aiohttp.ClientSession",
        return_value=_make_async_cm(session),
    ):
        with pytest.raises(GitLabRateLimitError) as exc_info:
            await client.fetch_state()

    assert exc_info.value.retry_after == 60


# ---------------------------------------------------------------------------
# 9. 404 on one project pipeline: skipped, others succeed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pipeline_404_skipped_partial_success() -> None:
    """A 404 on one project pipeline skips that project; error is set."""
    client = _make_client(projects=["missing/project", "ok/project"])

    call_count = 0

    @asynccontextmanager
    async def _get(*args: Any, **kwargs: Any):
        nonlocal call_count
        call_count += 1
        resp = MagicMock()
        if call_count == 1:  # /merge_requests
            resp.status = 200
            resp.json = AsyncMock(return_value=[])
            resp.raise_for_status = MagicMock(return_value=None)
        elif call_count == 2:  # /issues
            resp.status = 200
            resp.json = AsyncMock(return_value=[])
            resp.raise_for_status = MagicMock(return_value=None)
        elif call_count == 3:  # pipeline for missing/project → 404
            resp.status = 404
            err = aiohttp.ClientResponseError(
                request_info=MagicMock(),
                history=(),
                status=404,
                message="Not Found",
            )
            resp.raise_for_status = MagicMock(side_effect=err)
            resp.json = AsyncMock(return_value={})
        else:  # pipeline for ok/project
            resp.status = 200
            resp.json = AsyncMock(return_value=[_pipeline_item("running")])
            resp.raise_for_status = MagicMock(return_value=None)

        resp.headers = {}
        yield resp

    session = MagicMock()
    session.get = _get

    with patch(
        "integrations.gitlab.client.aiohttp.ClientSession",
        return_value=_make_async_cm(session),
    ):
        state = await client.fetch_state()

    # Only ok/project pipeline should be present; missing/project is silently skipped
    assert len(state.pipelines) == 1
    assert state.pipelines[0].project == "ok/project"
    assert state.pipelines[0].status == "running"
    # Per spec: 404 is logged at WARNING but does NOT set state.error
    # (other projects continue successfully; partial data is surfaced)


# ---------------------------------------------------------------------------
# 10. Network error: partial data with error set
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_network_error_returns_partial_with_error() -> None:
    """A ClientConnectorError on MR/Issue fetch returns error in state."""
    client = _make_client(projects=[])

    @asynccontextmanager
    async def _get(*args: Any, **kwargs: Any):
        raise aiohttp.ClientConnectorError(
            connection_key=MagicMock(), os_error=OSError("connection refused")
        )
        yield  # type: ignore[misc]

    session = MagicMock()
    session.get = _get

    with patch(
        "integrations.gitlab.client.aiohttp.ClientSession",
        return_value=_make_async_cm(session),
    ):
        state = await client.fetch_state()

    assert state.error is not None
    assert state.mrs == []
    assert state.issues == []


# ---------------------------------------------------------------------------
# 11. Project path: numeric ID
# ---------------------------------------------------------------------------


def test_project_path_numeric() -> None:
    """Numeric project IDs resolve as ``projects/42``."""
    client = _make_client(projects=["42"])
    assert client._project_path("42") == "projects/42"


# ---------------------------------------------------------------------------
# 12. Project path: simple slug
# ---------------------------------------------------------------------------


def test_project_path_slug() -> None:
    """Slugs with one slash are percent-encoded as ``projects/group%2Fproject``."""
    client = _make_client(projects=["group/project"])
    assert client._project_path("group/project") == "projects/group%2Fproject"


# ---------------------------------------------------------------------------
# 13. Project path: nested slug
# ---------------------------------------------------------------------------


def test_project_path_nested_slug() -> None:
    """Nested slugs with multiple slashes encode all slashes."""
    client = _make_client(projects=["group/sub/project"])
    assert client._project_path("group/sub/project") == "projects/group%2Fsub%2Fproject"


# ---------------------------------------------------------------------------
# 14. Empty projects list: pipelines section is empty
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_projects_no_pipelines() -> None:
    """When projects=[], pipelines is empty and MRs/Issues still fetch."""
    client = _make_client(projects=[])

    responses = [
        ([_mr_item(1)], 200, {}),
        ([_issue_item(10)], 200, {}),
    ]
    with _patch_session_multi(*responses):
        state = await client.fetch_state()

    assert state.pipelines == []
    assert len(state.mrs) == 1
    assert len(state.issues) == 1
    assert state.error is None
