"""Async GitHub REST v3 client for JARVIS.

Uses raw ``aiohttp`` — avoids the synchronous ``PyGithub`` wrapper that would
require thread-pool dispatch and adds heavy object-graph overhead.

All endpoints call ``https://api.github.com`` with a classic PAT
(``Authorization: Bearer <token>``).  The client honours the
``X-RateLimit-Remaining`` response header and raises
:class:`GitHubRateLimitError` when fewer than 50 requests remain.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Any, Literal

import aiohttp

from utils.logger import get_logger

logger = get_logger("github.client")

_BASE_URL = "https://api.github.com"
_TIMEOUT = aiohttp.ClientTimeout(total=10)
_RATE_LIMIT_HEADROOM = 5  # raise before this many requests remain (search API caps at 30/h)


# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------


@dataclass
class GithubPR:
    """A single open pull request."""

    id: str
    repo: str
    title: str
    author: str
    html_url: str
    updated_at: str  # ISO-8601


@dataclass
class GithubIssue:
    """A single open issue assigned to the authenticated user."""

    id: str
    repo: str
    title: str
    html_url: str
    updated_at: str  # ISO-8601


@dataclass
class GithubCIRun:
    """Latest GitHub Actions workflow run for a repo."""

    repo: str
    status: Literal["success", "failure", "running", "pending"]
    ran_at: str  # ISO-8601
    html_url: str


@dataclass
class GitHubStatePayload:
    """Aggregate GitHub state broadcast to the HUD frontend."""

    prs: list[GithubPR]
    issues: list[GithubIssue]
    ci: list[GithubCIRun]
    fetched_at: str  # ISO-8601
    stale: bool  # True when last poll failed; data is from previous tick


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class GitHubAuthError(Exception):
    """Raised when the GitHub API returns a 401 Unauthorized response."""


class GitHubRateLimitError(Exception):
    """Raised when the rate-limit headroom drops below the safety threshold."""


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class GitHubClient:
    """Async GitHub REST v3 client.

    Requires a pre-created ``aiohttp.ClientSession`` so the caller controls
    connection-pool lifecycle (typically the poller or tests).
    """

    def __init__(self, token: str, session: aiohttp.ClientSession) -> None:
        """Initialise the client.

        Args:
            token: Classic PAT with ``repo`` read and ``read:org`` scopes.
            session: Shared ``aiohttp.ClientSession`` for all requests.
        """
        self._token = token
        self._session = session
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _check_rate_limit(self, response: aiohttp.ClientResponse) -> None:
        """Raise :class:`GitHubRateLimitError` when headroom is low.

        Args:
            response: The aiohttp response object (headers already populated).
        """
        remaining_str = response.headers.get("X-RateLimit-Remaining")
        if remaining_str is not None:
            remaining = int(remaining_str)
            if remaining < _RATE_LIMIT_HEADROOM:
                raise GitHubRateLimitError(
                    f"Rate-limit headroom too low: {remaining} requests remaining"
                )

    async def _get(self, url: str, params: dict[str, str] | None = None) -> Any:
        """Perform a GET request and return parsed JSON.

        Args:
            url: Full URL to fetch.
            params: Optional query parameters.

        Returns:
            Parsed JSON body (dict or list).

        Raises:
            GitHubAuthError: On HTTP 401.
            GitHubRateLimitError: On HTTP 403/429 with exhausted quota, or
                when ``X-RateLimit-Remaining`` is below the headroom threshold.
            aiohttp.ClientError: On network / timeout errors.
        """
        async with self._session.get(
            url,
            headers=self._headers,
            params=params,
            timeout=_TIMEOUT,
        ) as resp:
            if resp.status == 401:
                raise GitHubAuthError(
                    f"GitHub API returned 401 Unauthorized for {url}"
                )
            if resp.status in (403, 429):
                remaining = resp.headers.get("X-RateLimit-Remaining", "unknown")
                raise GitHubRateLimitError(
                    f"GitHub rate limit hit (HTTP {resp.status}, remaining={remaining})"
                )
            resp.raise_for_status()
            self._check_rate_limit(resp)
            return await resp.json()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def fetch_my_prs(self, repos: list[str] | None = None) -> list[GithubPR]:
        """Fetch open pull requests involving the authenticated user.

        Uses the GitHub Search API with ``is:pr is:open involves:@me`` and
        optionally scopes results to the configured repo list.

        Args:
            repos: Optional whitelist of ``"owner/repo"`` strings.  When
                provided, only PRs from those repos are returned.

        Returns:
            List of :class:`GithubPR` items, newest-updated first.
        """
        query = "is:pr is:open involves:@me"
        if repos:
            repo_filter = " ".join(f"repo:{r}" for r in repos)
            query = f"{query} {repo_filter}"

        data = await self._get(
            f"{_BASE_URL}/search/issues",
            params={"q": query, "per_page": "20", "sort": "updated", "order": "desc"},
        )
        prs: list[GithubPR] = []
        for item in data.get("items", []):
            # Search results include both issues and PRs; skip plain issues.
            if "pull_request" not in item:
                continue
            repo_full = item.get("repository_url", "").split("repos/")[-1]
            prs.append(
                GithubPR(
                    id=str(item["id"]),
                    repo=repo_full,
                    title=item.get("title", ""),
                    author=item.get("user", {}).get("login", ""),
                    html_url=item.get("html_url", ""),
                    updated_at=item.get("updated_at", ""),
                )
            )
        logger.debug(f"fetch_my_prs: {len(prs)} PRs returned")
        return prs

    async def fetch_my_issues(self, repos: list[str] | None = None) -> list[GithubIssue]:
        """Fetch open issues assigned to the authenticated user.

        Uses the GitHub Search API with ``is:issue is:open assignee:@me`` and
        optionally scopes results to the configured repo list.

        Args:
            repos: Optional whitelist of ``"owner/repo"`` strings.

        Returns:
            List of :class:`GithubIssue` items, newest-updated first.
        """
        query = "is:issue is:open assignee:@me"
        if repos:
            repo_filter = " ".join(f"repo:{r}" for r in repos)
            query = f"{query} {repo_filter}"

        data = await self._get(
            f"{_BASE_URL}/search/issues",
            params={"q": query, "per_page": "20", "sort": "updated", "order": "desc"},
        )
        issues: list[GithubIssue] = []
        for item in data.get("items", []):
            repo_full = item.get("repository_url", "").split("repos/")[-1]
            issues.append(
                GithubIssue(
                    id=str(item["id"]),
                    repo=repo_full,
                    title=item.get("title", ""),
                    html_url=item.get("html_url", ""),
                    updated_at=item.get("updated_at", ""),
                )
            )
        logger.debug(f"fetch_my_issues: {len(issues)} issues returned")
        return issues

    async def fetch_ci_status(self, repo: str) -> GithubCIRun | None:
        """Fetch the latest GitHub Actions workflow run for a repo.

        Args:
            repo: ``"owner/repo"`` string.

        Returns:
            :class:`GithubCIRun` for the most-recent run, or ``None`` if the
            repo has no workflow runs yet.
        """
        data = await self._get(
            f"{_BASE_URL}/repos/{repo}/actions/runs",
            params={"per_page": "1"},
        )
        runs = data.get("workflow_runs", [])
        if not runs:
            logger.debug(f"fetch_ci_status({repo}): no runs found")
            return None

        run = runs[0]
        conclusion = run.get("conclusion")
        run_status = run.get("status", "queued")

        if run_status in ("in_progress", "queued"):
            status: Literal["success", "failure", "running", "pending"] = (
                "running" if run_status == "in_progress" else "pending"
            )
        elif conclusion == "success":
            status = "success"
        elif conclusion in ("failure", "timed_out", "cancelled"):
            status = "failure"
        else:
            status = "pending"

        ran_at = run.get("updated_at") or run.get("created_at") or datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat()

        return GithubCIRun(
            repo=repo,
            status=status,
            ran_at=ran_at,
            html_url=run.get("html_url", ""),
        )

    async def get_rate_limit(self) -> dict[str, Any]:
        """Fetch the current rate-limit status for the authenticated token.

        Returns:
            Parsed JSON body from ``GET /rate_limit``.
        """
        return await self._get(f"{_BASE_URL}/rate_limit")
