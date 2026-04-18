"""Async GitLab REST v4 client for JARVIS.

Uses raw ``aiohttp`` sessions — avoids the synchronous ``python-gitlab`` wrapper
that does not fit an asyncio-first runtime.

All GitLab endpoints use ``Authorization: Bearer <token>`` with the token
supplied via ``GITLAB_TOKEN`` in ``.env`` (read once at startup by ws_server
and injected here via the constructor).

Self-hosted instances are supported: pass ``url`` as ``https://gitlab.example.com``
(trailing slashes are normalised automatically).

Project resolution
------------------
Items in ``projects`` are resolved as follows:
- If the string contains a ``/`` it is treated as a URL-encoded path slug
  (``projects/{urllib.parse.quote(slug, safe='')}``) — handles ``group/sub/project``.
- Otherwise it is treated as a numeric project ID
  (``projects/{numeric_id}``).
"""

from __future__ import annotations

import asyncio
import urllib.parse
from dataclasses import dataclass, field
from typing import Any

import aiohttp

from utils.logger import get_logger

logger = get_logger("gitlab.client")

_PER_PAGE = 50
_REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=10)
_FETCH_STATE_TIMEOUT = 30  # asyncio.wait_for cap for the whole fetch_state call


# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------


@dataclass
class GitLabMR:
    """A single open GitLab merge request."""

    id: int
    iid: int
    title: str
    source_branch: str
    web_url: str
    author: str
    created_at: str  # ISO 8601
    draft: bool


@dataclass
class GitLabIssue:
    """A single open GitLab issue assigned to the authenticated user."""

    id: int
    iid: int
    title: str
    labels: list[str] = field(default_factory=list)
    web_url: str = ""
    author: str = ""
    created_at: str = ""


@dataclass
class GitLabPipeline:
    """The most recent pipeline for a configured project."""

    project: str  # slug or ID as provided in config
    status: str  # success | failed | running | pending | canceled | skipped
    web_url: str
    created_at: str  # ISO 8601


@dataclass
class GitLabState:
    """Aggregated GitLab state broadcast to the HUD frontend."""

    mrs: list[GitLabMR]
    issues: list[GitLabIssue]
    pipelines: list[GitLabPipeline]
    error: str | None = None  # set if any fetch failed; partial data still returned


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class GitLabAuthError(Exception):
    """Raised when the GitLab API returns a 401 Unauthorized response."""


class GitLabRateLimitError(Exception):
    """Raised on HTTP 429; carries the Retry-After duration in seconds."""

    def __init__(self, message: str, retry_after: int = 60) -> None:
        """Initialise with message and Retry-After duration.

        Args:
            message: Human-readable error message.
            retry_after: Seconds to wait before retrying (from Retry-After header).
        """
        super().__init__(message)
        self.retry_after = retry_after


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class GitLabClient:
    """Async GitLab REST v4 client.

    Args:
        token: Personal access token with ``api`` + ``read_repository`` scopes.
        url: Base URL of the GitLab instance (default ``https://gitlab.com``).
        projects: List of project identifiers — slugs (``group/project``) or
            numeric IDs as strings.
    """

    def __init__(self, token: str, url: str, projects: list[str]) -> None:
        """Initialise the client without opening a network connection."""
        # Normalise base URL: strip trailing slash.
        self._base_url = url.rstrip("/")
        self._token = token
        self._projects = projects
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _project_path(self, project: str) -> str:
        """Return the GitLab API sub-path for a project identifier.

        Args:
            project: Slug (``group/project``) or numeric ID string.

        Returns:
            URL fragment like ``projects/42`` or ``projects/group%2Fproject``.
        """
        if "/" in project:
            encoded = urllib.parse.quote(project, safe="")
            return f"projects/{encoded}"
        return f"projects/{project}"

    async def _get(
        self,
        session: aiohttp.ClientSession,
        path: str,
        params: dict[str, str] | None = None,
    ) -> Any:
        """Perform a GET request to the GitLab API v4.

        Args:
            session: Shared aiohttp session.
            path: API path relative to ``/api/v4/`` (no leading slash).
            params: Optional query parameters.

        Returns:
            Parsed JSON body (dict or list).

        Raises:
            GitLabAuthError: On HTTP 401.
            GitLabRateLimitError: On HTTP 429.
            aiohttp.ClientResponseError: On other 4xx/5xx responses.
            aiohttp.ClientError: On network/timeout failures.
        """
        url = f"{self._base_url}/api/v4/{path}"
        async with session.get(
            url,
            headers=self._headers,
            params=params or {},
            timeout=_REQUEST_TIMEOUT,
        ) as resp:
            if resp.status == 401:
                raise GitLabAuthError(
                    f"GitLab API returned 401 Unauthorized for {url} — check GITLAB_TOKEN"
                )
            if resp.status == 429:
                retry_after_raw = resp.headers.get("Retry-After", "60")
                try:
                    retry_after = int(retry_after_raw)
                except ValueError:
                    retry_after = 60
                retry_after = min(retry_after, 300)
                raise GitLabRateLimitError(
                    f"GitLab rate limit hit (HTTP 429, Retry-After={retry_after}s)",
                    retry_after=retry_after,
                )
            resp.raise_for_status()
            return await resp.json()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def fetch_state(self) -> GitLabState:
        """Fetch all GitLab data in one batch and return a :class:`GitLabState`.

        Makes parallel requests for MRs and Issues, then sequential pipeline
        requests per project.  A 10 s timeout applies per request; the whole
        call is capped at 30 s via ``asyncio.wait_for``.

        Partial failures (e.g. a 404 on one pipeline) are isolated: already-
        fetched data is returned and ``GitLabState.error`` is set to the first
        error message encountered.

        Returns:
            :class:`GitLabState` with ``error=None`` on full success.
        """
        async with aiohttp.ClientSession() as session:
            return await asyncio.wait_for(
                self._fetch_all(session),
                timeout=_FETCH_STATE_TIMEOUT,
            )

    async def _fetch_all(self, session: aiohttp.ClientSession) -> GitLabState:
        """Internal: run all GitLab fetches within an open session.

        Args:
            session: Open aiohttp session owned by the caller.

        Returns:
            Populated :class:`GitLabState`.
        """
        error: str | None = None

        # Fetch MRs and Issues in parallel.
        try:
            mrs, issues = await asyncio.gather(
                self._fetch_mrs(session),
                self._fetch_issues(session),
            )
        except GitLabAuthError as exc:
            # Auth error → short-circuit immediately; no partial data possible.
            return GitLabState(
                mrs=[],
                issues=[],
                pipelines=[],
                error=str(exc),
            )
        except GitLabRateLimitError:
            # Re-raise so the poller can honour Retry-After.
            raise
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            logger.warning(f"GitLab MR/Issue fetch failed: {exc}")
            mrs = []
            issues = []
            error = str(exc)

        # Fetch pipelines per project (sequential — partial failures isolated).
        pipelines: list[GitLabPipeline] = []
        for project in self._projects:
            try:
                pipeline = await self._fetch_latest_pipeline(session, project)
                if pipeline is not None:
                    pipelines.append(pipeline)
            except GitLabAuthError as exc:
                error = error or str(exc)
                logger.warning(f"GitLab pipeline auth error for {project}: {exc}")
            except aiohttp.ClientResponseError as exc:
                if exc.status == 404:
                    logger.warning(
                        f"GitLab project not found (404): {project} — skipping pipeline"
                    )
                else:
                    error = error or str(exc)
                    logger.warning(f"GitLab pipeline fetch error for {project}: {exc}")
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                error = error or str(exc)
                logger.warning(f"GitLab pipeline fetch network error for {project}: {exc}")

        return GitLabState(
            mrs=mrs,
            issues=issues,
            pipelines=pipelines,
            error=error,
        )

    async def _fetch_mrs(self, session: aiohttp.ClientSession) -> list[GitLabMR]:
        """Fetch open MRs assigned to the authenticated user.

        Args:
            session: Open aiohttp session.

        Returns:
            List of :class:`GitLabMR` items.
        """
        data = await self._get(
            session,
            "merge_requests",
            params={
                "scope": "assigned_to_me",
                "state": "opened",
                "per_page": str(_PER_PAGE),
            },
        )
        mrs: list[GitLabMR] = []
        for item in data:
            title: str = item.get("title", "")
            # GitLab prefixes draft MRs with "Draft:" or "WIP:" in the title.
            is_draft = bool(item.get("draft", False)) or title.startswith(
                ("Draft:", "WIP:")
            )
            mrs.append(
                GitLabMR(
                    id=int(item.get("id", 0)),
                    iid=int(item.get("iid", 0)),
                    title=title,
                    source_branch=item.get("source_branch", ""),
                    web_url=item.get("web_url", ""),
                    author=item.get("author", {}).get("username", ""),
                    created_at=item.get("created_at", ""),
                    draft=is_draft,
                )
            )
        logger.debug(f"GitLab: fetched {len(mrs)} open MRs")
        return mrs

    async def _fetch_issues(self, session: aiohttp.ClientSession) -> list[GitLabIssue]:
        """Fetch open issues assigned to the authenticated user.

        Args:
            session: Open aiohttp session.

        Returns:
            List of :class:`GitLabIssue` items.
        """
        data = await self._get(
            session,
            "issues",
            params={
                "scope": "assigned_to_me",
                "state": "opened",
                "per_page": str(_PER_PAGE),
            },
        )
        issues: list[GitLabIssue] = []
        for item in data:
            raw_labels = item.get("labels", [])
            # Labels may be dicts (older API) or plain strings (v4).
            labels: list[str] = [
                lbl.get("name", str(lbl)) if isinstance(lbl, dict) else str(lbl)
                for lbl in raw_labels
            ]
            issues.append(
                GitLabIssue(
                    id=int(item.get("id", 0)),
                    iid=int(item.get("iid", 0)),
                    title=item.get("title", ""),
                    labels=labels,
                    web_url=item.get("web_url", ""),
                    author=item.get("author", {}).get("username", ""),
                    created_at=item.get("created_at", ""),
                )
            )
        logger.debug(f"GitLab: fetched {len(issues)} open issues")
        return issues

    async def _fetch_latest_pipeline(
        self,
        session: aiohttp.ClientSession,
        project: str,
    ) -> GitLabPipeline | None:
        """Fetch the most recent pipeline for a project.

        Args:
            session: Open aiohttp session.
            project: Project slug (``group/project``) or numeric ID string.

        Returns:
            :class:`GitLabPipeline` for the most recent run, or ``None`` if
            the project has no pipelines yet.
        """
        path = f"{self._project_path(project)}/pipelines"
        data = await self._get(
            session,
            path,
            params={"per_page": "1", "order_by": "id", "sort": "desc"},
        )
        if not data:
            logger.debug(f"GitLab: no pipelines found for {project}")
            return None

        item = data[0]
        return GitLabPipeline(
            project=project,
            status=item.get("status", "unknown"),
            web_url=item.get("web_url", ""),
            created_at=item.get("created_at", ""),
        )

    async def close(self) -> None:
        """No-op — sessions are created per ``fetch_state`` call.

        Kept for API symmetry with other JARVIS integration clients.
        """
