"""GitLab integration package for JARVIS.

Exports:
    GitLabClient  — async REST v4 client (aiohttp-based).
    GitLabPoller  — background polling loop that pushes ``gitlab_state`` WS frames.
"""

from integrations.gitlab.client import (
    GitLabClient,
    GitLabIssue,
    GitLabMR,
    GitLabPipeline,
    GitLabState,
)
from integrations.gitlab.poller import GitLabPoller

__all__ = [
    "GitLabClient",
    "GitLabIssue",
    "GitLabMR",
    "GitLabPipeline",
    "GitLabPoller",
    "GitLabState",
]
