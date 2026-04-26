"""MCP tool registrations for the ``gitlab.*`` namespace.

Thin wrappers over :mod:`integrations.gitlab.client`.  Each handler opens a
fresh ``aiohttp.ClientSession`` (matching what ``GitLabClient.fetch_state``
already does internally) and delegates to existing client methods, then
flattens dataclass results to plain dicts.

Registered tools (3):
- ``gitlab_list_my_mrs``
- ``gitlab_list_pipelines``
- ``gitlab_get_pipeline_details``
"""

from __future__ import annotations

import os
from dataclasses import asdict
from typing import Any

import aiohttp

from api.mcp_server import register_tool
from integrations.gitlab.client import (
    GitLabAuthError,
    GitLabClient,
    GitLabRateLimitError,
)
from utils.logger import get_logger

logger = get_logger("mcp_tools.gitlab")

# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------


def _make_client(projects: list[str] | None = None) -> GitLabClient:
    """Build a GitLabClient from ambient environment variables."""
    token = os.environ.get("GITLAB_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "GITLAB_TOKEN is not set — cannot execute GitLab MCP tool"
        )
    url = (
        os.environ.get("GITLAB_URL", "").strip() or "https://gitlab.com"
    )
    return GitLabClient(token=token, url=url, projects=projects or [])


# ---------------------------------------------------------------------------
# gitlab_list_my_mrs
# ---------------------------------------------------------------------------


@register_tool(
    name="gitlab_list_my_mrs",
    description=(
        "List GitLab merge requests assigned to the authenticated user. "
        "Optionally filter by state and cap results with a limit."
    ),
    schema={
        "type": "object",
        "properties": {
            "state": {
                "type": "string",
                "enum": ["opened", "closed", "merged", "all"],
                "description": "Filter by MR state. Defaults to 'opened'.",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 100,
                "description": "Maximum number of MRs to return (default 20).",
            },
        },
        "required": [],
    },
)
async def gitlab_list_my_mrs(
    state: str = "opened",
    limit: int = 20,
) -> dict[str, Any]:
    """Return merge requests assigned to the authenticated GitLab user."""
    client = _make_client()
    async with aiohttp.ClientSession() as session:
        try:
            mrs = await client._fetch_mrs(session)  # noqa: SLF001
        except GitLabAuthError as exc:
            raise RuntimeError(f"GitLab authentication failed: {exc}") from exc
        except GitLabRateLimitError as exc:
            raise RuntimeError(
                f"GitLab rate limit exceeded (retry after {exc.retry_after}s): {exc}"
            ) from exc

    mr_list = [asdict(mr) for mr in mrs[:limit]]
    logger.debug(f"gitlab_list_my_mrs: returning {len(mr_list)} MRs")
    return {"mrs": mr_list, "total": len(mr_list)}


# ---------------------------------------------------------------------------
# gitlab_list_pipelines
# ---------------------------------------------------------------------------


@register_tool(
    name="gitlab_list_pipelines",
    description=(
        "Return the most recent pipeline for a GitLab project. "
        "project_id may be a numeric ID or a 'group/project' slug."
    ),
    schema={
        "type": "object",
        "properties": {
            "project_id": {
                "type": ["string", "integer"],
                "description": "Project slug ('group/project') or numeric project ID.",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 50,
                "description": "Maximum number of pipelines to return (default 10).",
            },
        },
        "required": ["project_id"],
    },
)
async def gitlab_list_pipelines(
    project_id: str | int,
    limit: int = 10,
) -> dict[str, Any]:
    """Return the most recent pipelines for a GitLab project."""
    project = str(project_id)
    client = _make_client(projects=[project])
    async with aiohttp.ClientSession() as session:
        try:
            pipeline = await client._fetch_latest_pipeline(  # noqa: SLF001
                session, project
            )
        except GitLabAuthError as exc:
            raise RuntimeError(f"GitLab authentication failed: {exc}") from exc
        except GitLabRateLimitError as exc:
            raise RuntimeError(
                f"GitLab rate limit exceeded (retry after {exc.retry_after}s): {exc}"
            ) from exc

    if pipeline is None:
        logger.debug(f"gitlab_list_pipelines({project!r}): no pipelines found")
        return {"project_id": project, "pipelines": [], "total": 0}

    pipeline_list = [asdict(pipeline)]
    logger.debug(
        f"gitlab_list_pipelines({project!r}): returning {len(pipeline_list)} pipeline(s)"
    )
    return {"project_id": project, "pipelines": pipeline_list, "total": len(pipeline_list)}


# ---------------------------------------------------------------------------
# gitlab_get_pipeline_details
# ---------------------------------------------------------------------------


@register_tool(
    name="gitlab_get_pipeline_details",
    description=(
        "Fetch details of a specific GitLab pipeline by project and pipeline ID."
    ),
    schema={
        "type": "object",
        "properties": {
            "project_id": {
                "type": ["string", "integer"],
                "description": "Project slug ('group/project') or numeric project ID.",
            },
            "pipeline_id": {
                "type": "integer",
                "description": "Numeric pipeline ID.",
            },
        },
        "required": ["project_id", "pipeline_id"],
    },
)
async def gitlab_get_pipeline_details(
    project_id: str | int,
    pipeline_id: int,
) -> dict[str, Any]:
    """Return detailed information about a specific GitLab pipeline."""
    project = str(project_id)
    client = _make_client(projects=[project])
    project_path = client._project_path(project)  # noqa: SLF001
    async with aiohttp.ClientSession() as session:
        try:
            data = await client._get(  # noqa: SLF001
                session,
                f"{project_path}/pipelines/{pipeline_id}",
            )
        except GitLabAuthError as exc:
            raise RuntimeError(f"GitLab authentication failed: {exc}") from exc
        except GitLabRateLimitError as exc:
            raise RuntimeError(
                f"GitLab rate limit exceeded (retry after {exc.retry_after}s): {exc}"
            ) from exc

    result: dict[str, Any] = {
        "project_id": project,
        "pipeline_id": pipeline_id,
        "id": data.get("id"),
        "status": data.get("status", "unknown"),
        "ref": data.get("ref", ""),
        "sha": data.get("sha", ""),
        "web_url": data.get("web_url", ""),
        "created_at": data.get("created_at", ""),
        "updated_at": data.get("updated_at", ""),
        "finished_at": data.get("finished_at"),
        "duration": data.get("duration"),
    }
    logger.debug(
        f"gitlab_get_pipeline_details({project!r}, {pipeline_id}): "
        f"status={result['status']}"
    )
    return result
