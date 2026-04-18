"""Unit tests for integrations.github.client.GitHubClient.

All HTTP calls are mocked via unittest.mock — no real network access.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from integrations.github.client import (
    GitHubAuthError,
    GitHubClient,
    GitHubRateLimitError,
    GithubCIRun,
    GithubIssue,
    GithubPR,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session(
    json_data: Any = None,
    status: int = 200,
    headers: dict[str, str] | None = None,
) -> MagicMock:
    """Return a mock ``aiohttp.ClientSession`` whose GET returns ``json_data``."""
    resp = MagicMock()
    resp.status = status
    resp.headers = headers or {"X-RateLimit-Remaining": "4999"}
    resp.raise_for_status = MagicMock(return_value=None)
    resp.json = AsyncMock(return_value=json_data or {})

    @asynccontextmanager
    async def _get(*args: Any, **kwargs: Any):
        yield resp

    session = MagicMock()
    session.get = _get
    return session


def _pr_item(pr_id: int = 1) -> dict[str, Any]:
    return {
        "id": pr_id,
        "title": f"Fix bug #{pr_id}",
        "html_url": f"https://github.com/owner/repo/pull/{pr_id}",
        "updated_at": "2024-01-15T10:00:00Z",
        "user": {"login": "alice"},
        "repository_url": "https://api.github.com/repos/owner/repo",
        "pull_request": {"url": f"https://api.github.com/repos/owner/repo/pulls/{pr_id}"},
    }


def _issue_item(issue_id: int = 10) -> dict[str, Any]:
    return {
        "id": issue_id,
        "title": f"Issue #{issue_id}",
        "html_url": f"https://github.com/owner/repo/issues/{issue_id}",
        "updated_at": "2024-01-14T09:00:00Z",
        "user": {"login": "bob"},
        "repository_url": "https://api.github.com/repos/owner/repo",
    }


def _workflow_run(
    status: str = "completed",
    conclusion: str = "success",
) -> dict[str, Any]:
    return {
        "id": 999,
        "status": status,
        "conclusion": conclusion,
        "html_url": "https://github.com/owner/repo/actions/runs/999",
        "updated_at": "2024-01-15T11:00:00Z",
    }


# ---------------------------------------------------------------------------
# fetch_my_prs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_my_prs_happy_path() -> None:
    """Returns a list of GithubPR on a successful search response."""
    session = _make_session({"items": [_pr_item(1), _pr_item(2)]})
    client = GitHubClient(token="ghp_test", session=session)

    prs = await client.fetch_my_prs()

    assert len(prs) == 2
    assert all(isinstance(p, GithubPR) for p in prs)
    assert prs[0].title == "Fix bug #1"
    assert prs[0].author == "alice"
    assert prs[0].repo == "owner/repo"


@pytest.mark.asyncio
async def test_fetch_my_prs_empty() -> None:
    """Returns an empty list when no PRs match."""
    session = _make_session({"items": []})
    client = GitHubClient(token="ghp_test", session=session)

    prs = await client.fetch_my_prs()
    assert prs == []


@pytest.mark.asyncio
async def test_fetch_my_prs_filters_plain_issues() -> None:
    """Items without a 'pull_request' key (plain issues) are skipped."""
    plain_issue = _issue_item(5)
    pr_with_key = _pr_item(3)
    session = _make_session({"items": [plain_issue, pr_with_key]})
    client = GitHubClient(token="ghp_test", session=session)

    prs = await client.fetch_my_prs()
    assert len(prs) == 1
    assert prs[0].id == "3"


@pytest.mark.asyncio
async def test_fetch_my_prs_401_raises_auth_error() -> None:
    """A 401 response raises GitHubAuthError."""
    session = _make_session(status=401)
    client = GitHubClient(token="ghp_bad", session=session)

    with pytest.raises(GitHubAuthError):
        await client.fetch_my_prs()


@pytest.mark.asyncio
async def test_fetch_my_prs_429_raises_rate_limit_error() -> None:
    """A 429 response raises GitHubRateLimitError."""
    session = _make_session(
        status=429,
        headers={"X-RateLimit-Remaining": "0"},
    )
    client = GitHubClient(token="ghp_test", session=session)

    with pytest.raises(GitHubRateLimitError):
        await client.fetch_my_prs()


@pytest.mark.asyncio
async def test_fetch_my_prs_403_raises_rate_limit_error() -> None:
    """A 403 response with rate-limit headers raises GitHubRateLimitError."""
    session = _make_session(
        status=403,
        headers={"X-RateLimit-Remaining": "0"},
    )
    client = GitHubClient(token="ghp_test", session=session)

    with pytest.raises(GitHubRateLimitError):
        await client.fetch_my_prs()


@pytest.mark.asyncio
async def test_fetch_my_prs_low_remaining_raises_rate_limit() -> None:
    """When X-RateLimit-Remaining < 50 on a 200 response, raises GitHubRateLimitError."""
    session = _make_session(
        json_data={"items": [_pr_item(1)]},
        status=200,
        headers={"X-RateLimit-Remaining": "10"},
    )
    client = GitHubClient(token="ghp_test", session=session)

    with pytest.raises(GitHubRateLimitError):
        await client.fetch_my_prs()


# ---------------------------------------------------------------------------
# fetch_my_issues
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_my_issues_happy_path() -> None:
    """Returns a list of GithubIssue on a successful response."""
    session = _make_session({"items": [_issue_item(10)]})
    client = GitHubClient(token="ghp_test", session=session)

    issues = await client.fetch_my_issues()

    assert len(issues) == 1
    assert isinstance(issues[0], GithubIssue)
    assert issues[0].title == "Issue #10"
    assert issues[0].repo == "owner/repo"


@pytest.mark.asyncio
async def test_fetch_my_issues_empty() -> None:
    """Returns an empty list when no issues match."""
    session = _make_session({"items": []})
    client = GitHubClient(token="ghp_test", session=session)

    issues = await client.fetch_my_issues()
    assert issues == []


# ---------------------------------------------------------------------------
# fetch_ci_status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_ci_status_success() -> None:
    """Maps 'completed' + 'success' conclusion to status='success'."""
    run = _workflow_run(status="completed", conclusion="success")
    session = _make_session({"workflow_runs": [run]})
    client = GitHubClient(token="ghp_test", session=session)

    result = await client.fetch_ci_status("owner/repo")

    assert isinstance(result, GithubCIRun)
    assert result.status == "success"
    assert result.repo == "owner/repo"


@pytest.mark.asyncio
async def test_fetch_ci_status_failure() -> None:
    """Maps 'completed' + 'failure' conclusion to status='failure'."""
    run = _workflow_run(status="completed", conclusion="failure")
    session = _make_session({"workflow_runs": [run]})
    client = GitHubClient(token="ghp_test", session=session)

    result = await client.fetch_ci_status("owner/repo")
    assert result is not None
    assert result.status == "failure"


@pytest.mark.asyncio
async def test_fetch_ci_status_in_progress() -> None:
    """Maps 'in_progress' run status to status='running'."""
    run = _workflow_run(status="in_progress", conclusion=None)
    session = _make_session({"workflow_runs": [run]})
    client = GitHubClient(token="ghp_test", session=session)

    result = await client.fetch_ci_status("owner/repo")
    assert result is not None
    assert result.status == "running"


@pytest.mark.asyncio
async def test_fetch_ci_status_queued() -> None:
    """Maps 'queued' run status to status='pending'."""
    run = _workflow_run(status="queued", conclusion=None)
    session = _make_session({"workflow_runs": [run]})
    client = GitHubClient(token="ghp_test", session=session)

    result = await client.fetch_ci_status("owner/repo")
    assert result is not None
    assert result.status == "pending"


@pytest.mark.asyncio
async def test_fetch_ci_status_no_runs() -> None:
    """Returns None when the repo has no workflow runs."""
    session = _make_session({"workflow_runs": []})
    client = GitHubClient(token="ghp_test", session=session)

    result = await client.fetch_ci_status("owner/empty-repo")
    assert result is None


@pytest.mark.asyncio
async def test_fetch_ci_status_401() -> None:
    """401 during CI fetch raises GitHubAuthError."""
    session = _make_session(status=401)
    client = GitHubClient(token="ghp_bad", session=session)

    with pytest.raises(GitHubAuthError):
        await client.fetch_ci_status("owner/repo")


# ---------------------------------------------------------------------------
# get_rate_limit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_rate_limit_returns_dict() -> None:
    """Returns the parsed rate-limit JSON dict."""
    rate_data = {"resources": {"core": {"limit": 5000, "remaining": 4999}}}
    session = _make_session(rate_data)
    client = GitHubClient(token="ghp_test", session=session)

    result = await client.get_rate_limit()
    assert result == rate_data
