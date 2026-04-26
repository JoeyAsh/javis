"""Unit tests for api/mcp_tools/gitlab_tools.py.

Mocks at the GitLabClient boundary (integrations.gitlab.client).
No live network calls are made.

Covered:
- gitlab_list_my_mrs: happy path, empty list, auth error, rate-limit error,
  limit slicing, missing GITLAB_TOKEN.
- gitlab_list_pipelines: happy path (pipeline found), no pipeline, auth error,
  rate-limit error.
- gitlab_get_pipeline_details: happy path, auth error, rate-limit error.
"""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fake domain objects
# ---------------------------------------------------------------------------


@dataclass
class _FakeMR:
    id: int = 1
    iid: int = 1
    title: str = "Add feature"
    source_branch: str = "feature/foo"
    web_url: str = "https://gitlab.com/owner/repo/-/merge_requests/1"
    author: str = "alice"
    created_at: str = "2025-01-01T10:00:00Z"
    draft: bool = False


@dataclass
class _FakePipeline:
    project: str = "owner/repo"
    status: str = "success"
    web_url: str = "https://gitlab.com/owner/repo/-/pipelines/100"
    created_at: str = "2025-01-01T11:00:00Z"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_client(
    mrs: list | None = None,
    pipeline: _FakePipeline | None = _FakePipeline(),
    get_response: dict | None = None,
    auth_error: bool = False,
    rate_error: bool = False,
) -> MagicMock:
    from integrations.gitlab.client import GitLabAuthError, GitLabRateLimitError

    client = MagicMock()
    client._project_path = MagicMock(return_value="projects/owner%2Frepo")

    if auth_error:
        exc = GitLabAuthError("401 Unauthorized")
        client._fetch_mrs = AsyncMock(side_effect=exc)
        client._fetch_latest_pipeline = AsyncMock(side_effect=exc)
        client._get = AsyncMock(side_effect=exc)
    elif rate_error:
        exc = GitLabRateLimitError("429 Too Many Requests", retry_after=30)
        client._fetch_mrs = AsyncMock(side_effect=exc)
        client._fetch_latest_pipeline = AsyncMock(side_effect=exc)
        client._get = AsyncMock(side_effect=exc)
    else:
        client._fetch_mrs = AsyncMock(return_value=mrs if mrs is not None else [])
        client._fetch_latest_pipeline = AsyncMock(return_value=pipeline)
        client._get = AsyncMock(return_value=get_response or {})

    return client


# ---------------------------------------------------------------------------
# gitlab_list_my_mrs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gitlab_list_my_mrs_happy_path_returns_mr_list(monkeypatch):
    """gitlab_list_my_mrs returns {'mrs': [...], 'total': N}."""
    monkeypatch.setenv("GITLAB_TOKEN", "glpat_test")
    fake_mr = _FakeMR()
    mock_client = _make_mock_client(mrs=[fake_mr])

    with patch("api.mcp_tools.gitlab_tools._make_client", return_value=mock_client), patch(
        "api.mcp_tools.gitlab_tools.aiohttp.ClientSession"
    ):
        from api.mcp_tools.gitlab_tools import gitlab_list_my_mrs

        result = await gitlab_list_my_mrs(state="opened", limit=20)

    assert "mrs" in result
    assert result["total"] == 1
    assert result["mrs"][0]["id"] == 1
    assert result["mrs"][0]["title"] == "Add feature"


@pytest.mark.asyncio
async def test_gitlab_list_my_mrs_empty_list(monkeypatch):
    """gitlab_list_my_mrs returns empty mrs list gracefully."""
    monkeypatch.setenv("GITLAB_TOKEN", "glpat_test")
    mock_client = _make_mock_client(mrs=[])

    with patch("api.mcp_tools.gitlab_tools._make_client", return_value=mock_client), patch(
        "api.mcp_tools.gitlab_tools.aiohttp.ClientSession"
    ):
        from api.mcp_tools.gitlab_tools import gitlab_list_my_mrs

        result = await gitlab_list_my_mrs()

    assert result == {"mrs": [], "total": 0}


@pytest.mark.asyncio
async def test_gitlab_list_my_mrs_limit_slices_result(monkeypatch):
    """gitlab_list_my_mrs respects the limit parameter."""
    monkeypatch.setenv("GITLAB_TOKEN", "glpat_test")
    mrs = [_FakeMR(id=i, iid=i) for i in range(10)]
    mock_client = _make_mock_client(mrs=mrs)

    with patch("api.mcp_tools.gitlab_tools._make_client", return_value=mock_client), patch(
        "api.mcp_tools.gitlab_tools.aiohttp.ClientSession"
    ):
        from api.mcp_tools.gitlab_tools import gitlab_list_my_mrs

        result = await gitlab_list_my_mrs(limit=4)

    assert result["total"] == 4
    assert len(result["mrs"]) == 4


@pytest.mark.asyncio
async def test_gitlab_list_my_mrs_auth_error_raises_runtime(monkeypatch):
    """gitlab_list_my_mrs re-raises auth error as RuntimeError."""
    monkeypatch.setenv("GITLAB_TOKEN", "glpat_test")
    mock_client = _make_mock_client(auth_error=True)

    with patch("api.mcp_tools.gitlab_tools._make_client", return_value=mock_client), patch(
        "api.mcp_tools.gitlab_tools.aiohttp.ClientSession"
    ):
        from api.mcp_tools.gitlab_tools import gitlab_list_my_mrs

        with pytest.raises(RuntimeError, match="authentication failed"):
            await gitlab_list_my_mrs()


@pytest.mark.asyncio
async def test_gitlab_list_my_mrs_rate_limit_raises_runtime(monkeypatch):
    """gitlab_list_my_mrs re-raises rate-limit error as RuntimeError."""
    monkeypatch.setenv("GITLAB_TOKEN", "glpat_test")
    mock_client = _make_mock_client(rate_error=True)

    with patch("api.mcp_tools.gitlab_tools._make_client", return_value=mock_client), patch(
        "api.mcp_tools.gitlab_tools.aiohttp.ClientSession"
    ):
        from api.mcp_tools.gitlab_tools import gitlab_list_my_mrs

        with pytest.raises(RuntimeError, match="rate limit"):
            await gitlab_list_my_mrs()


@pytest.mark.asyncio
async def test_gitlab_list_my_mrs_missing_token_raises_runtime(monkeypatch):
    """gitlab_list_my_mrs raises RuntimeError when GITLAB_TOKEN is absent."""
    monkeypatch.delenv("GITLAB_TOKEN", raising=False)

    with patch("api.mcp_tools.gitlab_tools.aiohttp.ClientSession"):
        from api.mcp_tools.gitlab_tools import gitlab_list_my_mrs

        with pytest.raises(RuntimeError, match="GITLAB_TOKEN"):
            await gitlab_list_my_mrs()


# ---------------------------------------------------------------------------
# gitlab_list_pipelines
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gitlab_list_pipelines_happy_path(monkeypatch):
    """gitlab_list_pipelines returns pipeline list when a pipeline exists."""
    monkeypatch.setenv("GITLAB_TOKEN", "glpat_test")
    fake_pipeline = _FakePipeline()
    mock_client = _make_mock_client(pipeline=fake_pipeline)

    with patch("api.mcp_tools.gitlab_tools._make_client", return_value=mock_client), patch(
        "api.mcp_tools.gitlab_tools.aiohttp.ClientSession"
    ):
        from api.mcp_tools.gitlab_tools import gitlab_list_pipelines

        result = await gitlab_list_pipelines(project_id="owner/repo")

    assert result["project_id"] == "owner/repo"
    assert result["total"] == 1
    assert result["pipelines"][0]["status"] == "success"


@pytest.mark.asyncio
async def test_gitlab_list_pipelines_no_pipeline_returns_empty(monkeypatch):
    """gitlab_list_pipelines returns empty list when no pipeline exists."""
    monkeypatch.setenv("GITLAB_TOKEN", "glpat_test")
    mock_client = _make_mock_client(pipeline=None)

    with patch("api.mcp_tools.gitlab_tools._make_client", return_value=mock_client), patch(
        "api.mcp_tools.gitlab_tools.aiohttp.ClientSession"
    ):
        from api.mcp_tools.gitlab_tools import gitlab_list_pipelines

        result = await gitlab_list_pipelines(project_id="owner/repo")

    assert result["pipelines"] == []
    assert result["total"] == 0


@pytest.mark.asyncio
async def test_gitlab_list_pipelines_passes_project_to_client(monkeypatch):
    """gitlab_list_pipelines constructs a client scoped to the given project."""
    monkeypatch.setenv("GITLAB_TOKEN", "glpat_test")
    mock_client = _make_mock_client(pipeline=None)

    with patch(
        "api.mcp_tools.gitlab_tools._make_client", return_value=mock_client
    ) as make_client_mock, patch("api.mcp_tools.gitlab_tools.aiohttp.ClientSession"):
        from api.mcp_tools.gitlab_tools import gitlab_list_pipelines

        await gitlab_list_pipelines(project_id="mygroup/myproject")

    make_client_mock.assert_called_once_with(projects=["mygroup/myproject"])


@pytest.mark.asyncio
async def test_gitlab_list_pipelines_auth_error_raises_runtime(monkeypatch):
    """gitlab_list_pipelines re-raises auth error as RuntimeError."""
    monkeypatch.setenv("GITLAB_TOKEN", "glpat_test")
    mock_client = _make_mock_client(auth_error=True)

    with patch("api.mcp_tools.gitlab_tools._make_client", return_value=mock_client), patch(
        "api.mcp_tools.gitlab_tools.aiohttp.ClientSession"
    ):
        from api.mcp_tools.gitlab_tools import gitlab_list_pipelines

        with pytest.raises(RuntimeError, match="authentication failed"):
            await gitlab_list_pipelines(project_id="owner/repo")


@pytest.mark.asyncio
async def test_gitlab_list_pipelines_rate_limit_raises_runtime(monkeypatch):
    """gitlab_list_pipelines re-raises rate-limit error as RuntimeError."""
    monkeypatch.setenv("GITLAB_TOKEN", "glpat_test")
    mock_client = _make_mock_client(rate_error=True)

    with patch("api.mcp_tools.gitlab_tools._make_client", return_value=mock_client), patch(
        "api.mcp_tools.gitlab_tools.aiohttp.ClientSession"
    ):
        from api.mcp_tools.gitlab_tools import gitlab_list_pipelines

        with pytest.raises(RuntimeError, match="rate limit"):
            await gitlab_list_pipelines(project_id="owner/repo")


# ---------------------------------------------------------------------------
# gitlab_get_pipeline_details
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gitlab_get_pipeline_details_happy_path(monkeypatch):
    """gitlab_get_pipeline_details returns mapped pipeline detail dict."""
    monkeypatch.setenv("GITLAB_TOKEN", "glpat_test")
    api_response = {
        "id": 100,
        "status": "success",
        "ref": "main",
        "sha": "abc123",
        "web_url": "https://gitlab.com/owner/repo/-/pipelines/100",
        "created_at": "2025-01-01T10:00:00Z",
        "updated_at": "2025-01-01T10:05:00Z",
        "finished_at": "2025-01-01T10:05:00Z",
        "duration": 300,
    }
    mock_client = _make_mock_client(get_response=api_response)

    with patch("api.mcp_tools.gitlab_tools._make_client", return_value=mock_client), patch(
        "api.mcp_tools.gitlab_tools.aiohttp.ClientSession"
    ):
        from api.mcp_tools.gitlab_tools import gitlab_get_pipeline_details

        result = await gitlab_get_pipeline_details(project_id="owner/repo", pipeline_id=100)

    assert result["project_id"] == "owner/repo"
    assert result["pipeline_id"] == 100
    assert result["status"] == "success"
    assert result["ref"] == "main"
    assert result["sha"] == "abc123"
    assert result["duration"] == 300


@pytest.mark.asyncio
async def test_gitlab_get_pipeline_details_empty_response_uses_defaults(monkeypatch):
    """gitlab_get_pipeline_details falls back to default values for missing fields."""
    monkeypatch.setenv("GITLAB_TOKEN", "glpat_test")
    mock_client = _make_mock_client(get_response={})

    with patch("api.mcp_tools.gitlab_tools._make_client", return_value=mock_client), patch(
        "api.mcp_tools.gitlab_tools.aiohttp.ClientSession"
    ):
        from api.mcp_tools.gitlab_tools import gitlab_get_pipeline_details

        result = await gitlab_get_pipeline_details(project_id="owner/repo", pipeline_id=99)

    assert result["status"] == "unknown"
    assert result["ref"] == ""


@pytest.mark.asyncio
async def test_gitlab_get_pipeline_details_calls_correct_path(monkeypatch):
    """gitlab_get_pipeline_details calls _get with the pipelines sub-path."""
    monkeypatch.setenv("GITLAB_TOKEN", "glpat_test")
    mock_client = _make_mock_client(get_response={})

    with patch("api.mcp_tools.gitlab_tools._make_client", return_value=mock_client), patch(
        "api.mcp_tools.gitlab_tools.aiohttp.ClientSession"
    ) as mock_session_cls:
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        from api.mcp_tools.gitlab_tools import gitlab_get_pipeline_details

        await gitlab_get_pipeline_details(project_id="owner/repo", pipeline_id=55)

    # Verify _get was called and the path arg contains the pipeline ID.
    assert mock_client._get.called
    path_arg = mock_client._get.call_args[0][1]
    assert "55" in path_arg


@pytest.mark.asyncio
async def test_gitlab_get_pipeline_details_auth_error_raises_runtime(monkeypatch):
    """gitlab_get_pipeline_details re-raises auth error as RuntimeError."""
    monkeypatch.setenv("GITLAB_TOKEN", "glpat_test")
    mock_client = _make_mock_client(auth_error=True)

    with patch("api.mcp_tools.gitlab_tools._make_client", return_value=mock_client), patch(
        "api.mcp_tools.gitlab_tools.aiohttp.ClientSession"
    ):
        from api.mcp_tools.gitlab_tools import gitlab_get_pipeline_details

        with pytest.raises(RuntimeError, match="authentication failed"):
            await gitlab_get_pipeline_details(project_id="owner/repo", pipeline_id=1)


@pytest.mark.asyncio
async def test_gitlab_get_pipeline_details_rate_limit_raises_runtime(monkeypatch):
    """gitlab_get_pipeline_details re-raises rate-limit error as RuntimeError."""
    monkeypatch.setenv("GITLAB_TOKEN", "glpat_test")
    mock_client = _make_mock_client(rate_error=True)

    with patch("api.mcp_tools.gitlab_tools._make_client", return_value=mock_client), patch(
        "api.mcp_tools.gitlab_tools.aiohttp.ClientSession"
    ):
        from api.mcp_tools.gitlab_tools import gitlab_get_pipeline_details

        with pytest.raises(RuntimeError, match="rate limit"):
            await gitlab_get_pipeline_details(project_id="owner/repo", pipeline_id=1)
