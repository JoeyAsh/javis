"""Unit tests for api/mcp_tools/github_tools.py.

Mocks at the GitHubClient boundary (integrations.github.client).
No live network calls are made.

Covered:
- github_list_my_prs: happy path, empty list, auth error, rate-limit error,
  missing GITHUB_TOKEN.
- github_list_repo_issues: happy path, empty result, auth error,
  rate-limit error, limit slicing.
- github_get_pr_details: happy path, auth error, rate-limit error.
- github_get_ci_status: happy path (run found), no runs, auth error.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Tiny domain-object stubs (mirror the real dataclasses to avoid aiohttp deps)
# ---------------------------------------------------------------------------


@dataclass
class _FakePR:
    id: str = "pr-1"
    repo: str = "owner/repo"
    title: str = "Fix the bug"
    author: str = "alice"
    html_url: str = "https://github.com/owner/repo/pull/1"
    updated_at: str = "2025-01-01T12:00:00Z"


@dataclass
class _FakeIssue:
    id: str = "issue-1"
    repo: str = "owner/repo"
    title: str = "Broken widget"
    html_url: str = "https://github.com/owner/repo/issues/1"
    updated_at: str = "2025-01-01T09:00:00Z"


@dataclass
class _FakeCIRun:
    repo: str = "owner/repo"
    status: str = "success"
    ran_at: str = "2025-01-01T11:00:00Z"
    html_url: str = "https://github.com/owner/repo/actions/runs/1"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_client(
    prs: list | None = None,
    issues: list | None = None,
    ci_run: Any = None,
    pr_detail: dict | None = None,
    auth_error: bool = False,
    rate_error: bool = False,
) -> MagicMock:
    """Return a MagicMock GitHubClient with preconfigured async methods."""
    from integrations.github.client import GitHubAuthError, GitHubRateLimitError

    client = MagicMock()

    if auth_error:
        exc = GitHubAuthError("401 Unauthorized")
        client.fetch_my_prs = AsyncMock(side_effect=exc)
        client.fetch_my_issues = AsyncMock(side_effect=exc)
        client.fetch_ci_status = AsyncMock(side_effect=exc)
        client._get = AsyncMock(side_effect=exc)
    elif rate_error:
        exc = GitHubRateLimitError("rate limit")
        client.fetch_my_prs = AsyncMock(side_effect=exc)
        client.fetch_my_issues = AsyncMock(side_effect=exc)
        client.fetch_ci_status = AsyncMock(side_effect=exc)
        client._get = AsyncMock(side_effect=exc)
    else:
        client.fetch_my_prs = AsyncMock(return_value=prs if prs is not None else [])
        client.fetch_my_issues = AsyncMock(return_value=issues if issues is not None else [])
        client.fetch_ci_status = AsyncMock(return_value=ci_run)
        client._get = AsyncMock(return_value=pr_detail or {})

    return client


# ---------------------------------------------------------------------------
# github_list_my_prs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_github_list_my_prs_happy_path_returns_pr_list(monkeypatch):
    """github_list_my_prs returns {'prs': [...], 'total': N} for a valid token."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    fake_pr = _FakePR()
    mock_client = _make_mock_client(prs=[fake_pr])

    with patch(
        "api.mcp_tools.github_tools._make_client", return_value=mock_client
    ), patch("api.mcp_tools.github_tools.aiohttp.ClientSession"):
        from api.mcp_tools.github_tools import github_list_my_prs

        result = await github_list_my_prs(state="open", limit=20)

    assert "prs" in result
    assert "total" in result
    assert result["total"] == 1
    assert result["prs"][0]["id"] == "pr-1"
    assert result["prs"][0]["title"] == "Fix the bug"


@pytest.mark.asyncio
async def test_github_list_my_prs_empty_returns_empty_list(monkeypatch):
    """github_list_my_prs returns empty prs list when no PRs are open."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    mock_client = _make_mock_client(prs=[])

    with patch(
        "api.mcp_tools.github_tools._make_client", return_value=mock_client
    ), patch("api.mcp_tools.github_tools.aiohttp.ClientSession"):
        from api.mcp_tools.github_tools import github_list_my_prs

        result = await github_list_my_prs()

    assert result == {"prs": [], "total": 0}


@pytest.mark.asyncio
async def test_github_list_my_prs_limit_slices_result(monkeypatch):
    """github_list_my_prs respects the limit parameter."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    prs = [_FakePR(id=f"pr-{i}") for i in range(10)]
    mock_client = _make_mock_client(prs=prs)

    with patch(
        "api.mcp_tools.github_tools._make_client", return_value=mock_client
    ), patch("api.mcp_tools.github_tools.aiohttp.ClientSession"):
        from api.mcp_tools.github_tools import github_list_my_prs

        result = await github_list_my_prs(limit=3)

    assert result["total"] == 3
    assert len(result["prs"]) == 3


@pytest.mark.asyncio
async def test_github_list_my_prs_auth_error_raises_runtime(monkeypatch):
    """github_list_my_prs re-raises GitHubAuthError as RuntimeError."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    mock_client = _make_mock_client(auth_error=True)

    with patch(
        "api.mcp_tools.github_tools._make_client", return_value=mock_client
    ), patch("api.mcp_tools.github_tools.aiohttp.ClientSession"):
        from api.mcp_tools.github_tools import github_list_my_prs

        with pytest.raises(RuntimeError, match="authentication failed"):
            await github_list_my_prs()


@pytest.mark.asyncio
async def test_github_list_my_prs_rate_limit_error_raises_runtime(monkeypatch):
    """github_list_my_prs re-raises GitHubRateLimitError as RuntimeError."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    mock_client = _make_mock_client(rate_error=True)

    with patch(
        "api.mcp_tools.github_tools._make_client", return_value=mock_client
    ), patch("api.mcp_tools.github_tools.aiohttp.ClientSession"):
        from api.mcp_tools.github_tools import github_list_my_prs

        with pytest.raises(RuntimeError, match="rate limit"):
            await github_list_my_prs()


@pytest.mark.asyncio
async def test_github_list_my_prs_missing_token_raises_runtime(monkeypatch):
    """github_list_my_prs raises RuntimeError when GITHUB_TOKEN is absent."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    # Do NOT patch _make_client — we want the real guard to fire.
    with patch("api.mcp_tools.github_tools.aiohttp.ClientSession"):
        from api.mcp_tools.github_tools import github_list_my_prs

        with pytest.raises(RuntimeError, match="GITHUB_TOKEN"):
            await github_list_my_prs()


# ---------------------------------------------------------------------------
# github_list_repo_issues
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_github_list_repo_issues_happy_path(monkeypatch):
    """github_list_repo_issues returns issues list for a given repo."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    fake_issue = _FakeIssue()
    mock_client = _make_mock_client(issues=[fake_issue])

    with patch(
        "api.mcp_tools.github_tools._make_client", return_value=mock_client
    ), patch("api.mcp_tools.github_tools.aiohttp.ClientSession"):
        from api.mcp_tools.github_tools import github_list_repo_issues

        result = await github_list_repo_issues(repo="owner/repo")

    assert result["repo"] == "owner/repo"
    assert result["total"] == 1
    assert result["issues"][0]["id"] == "issue-1"


@pytest.mark.asyncio
async def test_github_list_repo_issues_passes_repo_to_client(monkeypatch):
    """github_list_repo_issues passes repos=[repo] to client.fetch_my_issues."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    mock_client = _make_mock_client(issues=[])

    with patch(
        "api.mcp_tools.github_tools._make_client", return_value=mock_client
    ), patch("api.mcp_tools.github_tools.aiohttp.ClientSession"):
        from api.mcp_tools.github_tools import github_list_repo_issues

        await github_list_repo_issues(repo="my/project")

    mock_client.fetch_my_issues.assert_called_once_with(repos=["my/project"])


@pytest.mark.asyncio
async def test_github_list_repo_issues_empty_result(monkeypatch):
    """github_list_repo_issues returns empty issues list gracefully."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    mock_client = _make_mock_client(issues=[])

    with patch(
        "api.mcp_tools.github_tools._make_client", return_value=mock_client
    ), patch("api.mcp_tools.github_tools.aiohttp.ClientSession"):
        from api.mcp_tools.github_tools import github_list_repo_issues

        result = await github_list_repo_issues(repo="owner/repo")

    assert result["issues"] == []
    assert result["total"] == 0


@pytest.mark.asyncio
async def test_github_list_repo_issues_auth_error_raises_runtime(monkeypatch):
    """github_list_repo_issues re-raises auth errors as RuntimeError."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    mock_client = _make_mock_client(auth_error=True)

    with patch(
        "api.mcp_tools.github_tools._make_client", return_value=mock_client
    ), patch("api.mcp_tools.github_tools.aiohttp.ClientSession"):
        from api.mcp_tools.github_tools import github_list_repo_issues

        with pytest.raises(RuntimeError, match="authentication failed"):
            await github_list_repo_issues(repo="owner/repo")


@pytest.mark.asyncio
async def test_github_list_repo_issues_rate_limit_raises_runtime(monkeypatch):
    """github_list_repo_issues re-raises rate-limit errors as RuntimeError."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    mock_client = _make_mock_client(rate_error=True)

    with patch(
        "api.mcp_tools.github_tools._make_client", return_value=mock_client
    ), patch("api.mcp_tools.github_tools.aiohttp.ClientSession"):
        from api.mcp_tools.github_tools import github_list_repo_issues

        with pytest.raises(RuntimeError, match="rate limit"):
            await github_list_repo_issues(repo="owner/repo")


# ---------------------------------------------------------------------------
# github_get_pr_details
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_github_get_pr_details_happy_path_maps_fields(monkeypatch):
    """github_get_pr_details returns a dict with the expected mapped fields."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    api_response = {
        "title": "Add feature X",
        "state": "open",
        "user": {"login": "bob"},
        "html_url": "https://github.com/owner/repo/pull/42",
        "body": "PR body",
        "draft": False,
        "created_at": "2025-01-01T10:00:00Z",
        "updated_at": "2025-01-02T10:00:00Z",
        "merged_at": None,
        "head": {"ref": "feature-x"},
        "base": {"ref": "main"},
        "additions": 10,
        "deletions": 2,
        "changed_files": 3,
    }
    mock_client = _make_mock_client(pr_detail=api_response)

    with patch(
        "api.mcp_tools.github_tools._make_client", return_value=mock_client
    ), patch("api.mcp_tools.github_tools.aiohttp.ClientSession"):
        from api.mcp_tools.github_tools import github_get_pr_details

        result = await github_get_pr_details(repo="owner/repo", number=42)

    assert result["title"] == "Add feature X"
    assert result["state"] == "open"
    assert result["author"] == "bob"
    assert result["repo"] == "owner/repo"
    assert result["number"] == 42
    assert result["head_ref"] == "feature-x"
    assert result["base_ref"] == "main"
    assert result["additions"] == 10
    assert result["deletions"] == 2
    assert result["changed_files"] == 3


@pytest.mark.asyncio
async def test_github_get_pr_details_calls_correct_url(monkeypatch):
    """github_get_pr_details calls client._get with the expected GitHub API URL."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    mock_client = _make_mock_client(pr_detail={})

    with patch(
        "api.mcp_tools.github_tools._make_client", return_value=mock_client
    ), patch("api.mcp_tools.github_tools.aiohttp.ClientSession"):
        from api.mcp_tools.github_tools import github_get_pr_details

        await github_get_pr_details(repo="owner/repo", number=99)

    called_url = mock_client._get.call_args[0][0]
    assert called_url == "https://api.github.com/repos/owner/repo/pulls/99"


@pytest.mark.asyncio
async def test_github_get_pr_details_auth_error_raises_runtime(monkeypatch):
    """github_get_pr_details re-raises auth error as RuntimeError."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    mock_client = _make_mock_client(auth_error=True)

    with patch(
        "api.mcp_tools.github_tools._make_client", return_value=mock_client
    ), patch("api.mcp_tools.github_tools.aiohttp.ClientSession"):
        from api.mcp_tools.github_tools import github_get_pr_details

        with pytest.raises(RuntimeError, match="authentication failed"):
            await github_get_pr_details(repo="owner/repo", number=1)


@pytest.mark.asyncio
async def test_github_get_pr_details_rate_limit_raises_runtime(monkeypatch):
    """github_get_pr_details re-raises rate-limit error as RuntimeError."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    mock_client = _make_mock_client(rate_error=True)

    with patch(
        "api.mcp_tools.github_tools._make_client", return_value=mock_client
    ), patch("api.mcp_tools.github_tools.aiohttp.ClientSession"):
        from api.mcp_tools.github_tools import github_get_pr_details

        with pytest.raises(RuntimeError, match="rate limit"):
            await github_get_pr_details(repo="owner/repo", number=1)


# ---------------------------------------------------------------------------
# github_get_ci_status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_github_get_ci_status_happy_path_returns_run(monkeypatch):
    """github_get_ci_status returns CI run details when a run exists."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    fake_run = _FakeCIRun()
    mock_client = _make_mock_client(ci_run=fake_run)

    with patch(
        "api.mcp_tools.github_tools._make_client", return_value=mock_client
    ), patch("api.mcp_tools.github_tools.aiohttp.ClientSession"):
        from api.mcp_tools.github_tools import github_get_ci_status

        result = await github_get_ci_status(repo="owner/repo", ref="main")

    assert result["status"] == "success"
    assert result["ref"] == "main"
    assert "html_url" in result


@pytest.mark.asyncio
async def test_github_get_ci_status_no_runs_returns_no_runs_sentinel(monkeypatch):
    """github_get_ci_status returns status='no_runs' when client returns None."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    mock_client = _make_mock_client(ci_run=None)

    with patch(
        "api.mcp_tools.github_tools._make_client", return_value=mock_client
    ), patch("api.mcp_tools.github_tools.aiohttp.ClientSession"):
        from api.mcp_tools.github_tools import github_get_ci_status

        result = await github_get_ci_status(repo="owner/repo", ref="feature")

    assert result["status"] == "no_runs"
    assert result["repo"] == "owner/repo"
    assert result["ref"] == "feature"


@pytest.mark.asyncio
async def test_github_get_ci_status_calls_client_with_correct_repo(monkeypatch):
    """github_get_ci_status calls client.fetch_ci_status(repo)."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    mock_client = _make_mock_client(ci_run=None)

    with patch(
        "api.mcp_tools.github_tools._make_client", return_value=mock_client
    ), patch("api.mcp_tools.github_tools.aiohttp.ClientSession"):
        from api.mcp_tools.github_tools import github_get_ci_status

        await github_get_ci_status(repo="myorg/myrepo", ref="develop")

    mock_client.fetch_ci_status.assert_called_once_with("myorg/myrepo")


@pytest.mark.asyncio
async def test_github_get_ci_status_auth_error_raises_runtime(monkeypatch):
    """github_get_ci_status re-raises auth error as RuntimeError."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    mock_client = _make_mock_client(auth_error=True)

    with patch(
        "api.mcp_tools.github_tools._make_client", return_value=mock_client
    ), patch("api.mcp_tools.github_tools.aiohttp.ClientSession"):
        from api.mcp_tools.github_tools import github_get_ci_status

        with pytest.raises(RuntimeError, match="authentication failed"):
            await github_get_ci_status(repo="owner/repo", ref="main")


@pytest.mark.asyncio
async def test_github_get_ci_status_rate_limit_raises_runtime(monkeypatch):
    """github_get_ci_status re-raises rate-limit error as RuntimeError."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    mock_client = _make_mock_client(rate_error=True)

    with patch(
        "api.mcp_tools.github_tools._make_client", return_value=mock_client
    ), patch("api.mcp_tools.github_tools.aiohttp.ClientSession"):
        from api.mcp_tools.github_tools import github_get_ci_status

        with pytest.raises(RuntimeError, match="rate limit"):
            await github_get_ci_status(repo="owner/repo", ref="main")
