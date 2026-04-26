"""MCP tool registrations for the ``github.*`` namespace.

Thin wrappers over :mod:`integrations.github.client`.  No new business
logic — each handler creates a short-lived ``aiohttp.ClientSession`` and
delegates to the existing :class:`~integrations.github.client.GitHubClient`
methods, then converts the dataclass results to plain dicts for JSON
serialisation.

Registered tools (4):
- ``github_list_my_prs``
- ``github_list_repo_issues``
- ``github_get_pr_details``
- ``github_get_ci_status``
"""

from __future__ import annotations

import os
from dataclasses import asdict
from typing import Any

import aiohttp

from api.mcp_server import register_tool
from integrations.github.client import (
    GitHubAuthError,
    GitHubClient,
    GitHubRateLimitError,
)
from utils.logger import get_logger

logger = get_logger("mcp_tools.github")

# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------


def _make_client(session: aiohttp.ClientSession) -> GitHubClient:
    """Build a GitHubClient from the ambient environment token."""
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "GITHUB_TOKEN is not set — cannot execute GitHub MCP tool"
        )
    return GitHubClient(token=token, session=session)


# ---------------------------------------------------------------------------
# github_list_my_prs
# ---------------------------------------------------------------------------


@register_tool(
    name="github_list_my_prs",
    description=(
        "List open pull requests that involve the authenticated GitHub user "
        "(authored, assigned, or review-requested). Optionally filter by state "
        "and cap results with a limit."
    ),
    schema={
        "type": "object",
        "properties": {
            "state": {
                "type": "string",
                "enum": ["open", "closed", "all"],
                "description": "Filter by PR state. Defaults to 'open'.",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 100,
                "description": "Maximum number of PRs to return (default 20).",
            },
        },
        "required": [],
    },
)
async def github_list_my_prs(
    state: str = "open",
    limit: int = 20,
) -> dict[str, Any]:
    """Return open PRs involving the authenticated GitHub user."""
    async with aiohttp.ClientSession() as session:
        client = _make_client(session)
        try:
            prs = await client.fetch_my_prs()
        except GitHubAuthError as exc:
            raise RuntimeError(f"GitHub authentication failed: {exc}") from exc
        except GitHubRateLimitError as exc:
            raise RuntimeError(f"GitHub rate limit exceeded: {exc}") from exc

    pr_list = [asdict(pr) for pr in prs[:limit]]
    logger.debug(f"github_list_my_prs: returning {len(pr_list)} PRs")
    return {"prs": pr_list, "total": len(pr_list)}


# ---------------------------------------------------------------------------
# github_list_repo_issues
# ---------------------------------------------------------------------------


@register_tool(
    name="github_list_repo_issues",
    description=(
        "List open issues assigned to the authenticated GitHub user, optionally "
        "scoped to a specific repository."
    ),
    schema={
        "type": "object",
        "properties": {
            "repo": {
                "type": "string",
                "description": "Repository in 'owner/repo' format to scope the search.",
            },
            "state": {
                "type": "string",
                "enum": ["open", "closed", "all"],
                "description": "Filter by issue state. Defaults to 'open'.",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 100,
                "description": "Maximum number of issues to return (default 20).",
            },
        },
        "required": ["repo"],
    },
)
async def github_list_repo_issues(
    repo: str,
    state: str = "open",
    limit: int = 20,
) -> dict[str, Any]:
    """Return issues assigned to the authenticated user, scoped to repo."""
    async with aiohttp.ClientSession() as session:
        client = _make_client(session)
        try:
            issues = await client.fetch_my_issues(repos=[repo])
        except GitHubAuthError as exc:
            raise RuntimeError(f"GitHub authentication failed: {exc}") from exc
        except GitHubRateLimitError as exc:
            raise RuntimeError(f"GitHub rate limit exceeded: {exc}") from exc

    issue_list = [asdict(issue) for issue in issues[:limit]]
    logger.debug(
        f"github_list_repo_issues({repo!r}): returning {len(issue_list)} issues"
    )
    return {"issues": issue_list, "total": len(issue_list), "repo": repo}


# ---------------------------------------------------------------------------
# github_get_pr_details
# ---------------------------------------------------------------------------


@register_tool(
    name="github_get_pr_details",
    description=(
        "Fetch details of a specific pull request by repository and PR number."
    ),
    schema={
        "type": "object",
        "properties": {
            "repo": {
                "type": "string",
                "description": "Repository in 'owner/repo' format.",
            },
            "number": {
                "type": "integer",
                "description": "Pull request number.",
            },
        },
        "required": ["repo", "number"],
    },
)
async def github_get_pr_details(
    repo: str,
    number: int,
) -> dict[str, Any]:
    """Return detailed information about a single GitHub pull request."""
    async with aiohttp.ClientSession() as session:
        client = _make_client(session)
        try:
            data = await client._get(  # noqa: SLF001  # thin wrapper — no higher-level method exists
                f"https://api.github.com/repos/{repo}/pulls/{number}"
            )
        except GitHubAuthError as exc:
            raise RuntimeError(f"GitHub authentication failed: {exc}") from exc
        except GitHubRateLimitError as exc:
            raise RuntimeError(f"GitHub rate limit exceeded: {exc}") from exc

    result: dict[str, Any] = {
        "repo": repo,
        "number": number,
        "title": data.get("title", ""),
        "state": data.get("state", ""),
        "author": data.get("user", {}).get("login", ""),
        "html_url": data.get("html_url", ""),
        "body": data.get("body") or "",
        "draft": bool(data.get("draft", False)),
        "created_at": data.get("created_at", ""),
        "updated_at": data.get("updated_at", ""),
        "merged_at": data.get("merged_at"),
        "head_ref": data.get("head", {}).get("ref", ""),
        "base_ref": data.get("base", {}).get("ref", ""),
        "additions": data.get("additions", 0),
        "deletions": data.get("deletions", 0),
        "changed_files": data.get("changed_files", 0),
    }
    logger.debug(f"github_get_pr_details({repo}#{number}): fetched")
    return result


# ---------------------------------------------------------------------------
# github_get_ci_status
# ---------------------------------------------------------------------------


@register_tool(
    name="github_get_ci_status",
    description=(
        "Return the latest GitHub Actions CI status for a repository branch or ref."
    ),
    schema={
        "type": "object",
        "properties": {
            "repo": {
                "type": "string",
                "description": "Repository in 'owner/repo' format.",
            },
            "ref": {
                "type": "string",
                "description": "Branch name, tag, or commit SHA to query CI for.",
            },
        },
        "required": ["repo", "ref"],
    },
)
async def github_get_ci_status(
    repo: str,
    ref: str,
) -> dict[str, Any]:
    """Return the most recent CI workflow run status for a repo/ref."""
    async with aiohttp.ClientSession() as session:
        client = _make_client(session)
        try:
            run = await client.fetch_ci_status(repo)
        except GitHubAuthError as exc:
            raise RuntimeError(f"GitHub authentication failed: {exc}") from exc
        except GitHubRateLimitError as exc:
            raise RuntimeError(f"GitHub rate limit exceeded: {exc}") from exc

    if run is None:
        logger.debug(f"github_get_ci_status({repo}, {ref!r}): no runs found")
        return {"repo": repo, "ref": ref, "status": "no_runs", "html_url": ""}

    result = asdict(run)
    result["ref"] = ref
    logger.debug(f"github_get_ci_status({repo}, {ref!r}): status={run.status}")
    return result
