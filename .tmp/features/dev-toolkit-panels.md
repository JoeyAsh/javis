# Feature Spec: Developer Toolkit Panels

## Summary
Implement software-engineer-centric panels for the HUD: GitHub notifications and PR reviews, local repository status watcher, Docker container monitoring, CI build status, and extended system metrics (CPU/GPU temps, network throughput). These panels provide at-a-glance awareness of development environment state without context-switching.

## Goals
- Display GitHub notification count and PRs awaiting review
- Monitor local git repositories for dirty/ahead/behind status
- Show running Docker containers with resource usage
- Display GitHub Actions CI build status for watched repos
- Extend system metrics with GPU utilization, temperatures, and network I/O
- Enable voice queries: "how are my repos", "any PRs to review", "show containers"

## Non-Goals
- GitHub issue management (create/close issues)
- Docker container creation/deletion (read-only monitoring)
- CI trigger/restart from JARVIS
- Kubernetes/cloud container orchestration
- IDE integration or code editing
- Package vulnerability scanning (CVE alerts deferred to Phase B)

---

## Architecture

### Backend Components

```
src/integrations/
  github/
    __init__.py
    client.py           # GitHubClient - PyGithub wrapper
  docker/
    __init__.py
    client.py           # DockerClient - docker-py wrapper
  system/
    __init__.py
    metrics.py          # Extended system metrics collector

src/brain/agents/
  dev_toolkit_agent.py  # DevToolkitAgent - handles DEV_TOOLKIT intents
```

### Frontend Components

```
frontend/src/
  components/panels/
    DevPanel.tsx        # Combined GitHub + repos + Docker + CI
    SystemPanel.tsx     # Extended system metrics (update existing)
  hooks/
    useDevToolkit.ts
    useSystemMetrics.ts (update existing)
```

---

## GitHub Client (`src/integrations/github/client.py`)

### Interface

```python
from dataclasses import dataclass
from typing import Any
from datetime import datetime

@dataclass
class GitHubNotification:
    """GitHub notification."""
    id: str
    repo: str
    title: str
    type: str  # "PullRequest", "Issue", "Release", etc.
    reason: str  # "review_requested", "mention", "subscribed", etc.
    url: str
    updated_at: datetime
    unread: bool

@dataclass
class PullRequest:
    """Pull request summary."""
    id: int
    repo: str
    number: int
    title: str
    author: str
    state: str  # "open", "closed", "merged"
    draft: bool
    review_requested: bool
    url: str
    created_at: datetime
    updated_at: datetime

@dataclass
class WorkflowRun:
    """GitHub Actions workflow run."""
    id: int
    repo: str
    workflow_name: str
    branch: str
    status: str  # "queued", "in_progress", "completed"
    conclusion: str | None  # "success", "failure", "cancelled", etc.
    url: str
    created_at: datetime

class GitHubClient:
    """Async GitHub client wrapping PyGithub."""

    def __init__(self, token: str, config: dict[str, Any]) -> None:
        """Initialize with PAT.

        Args:
            token: GitHub Personal Access Token
            config: dev_toolkit.github section from config
        """
        ...

    async def initialize(self) -> None:
        """Verify token and connection."""
        ...

    async def get_notifications(self, unread_only: bool = True) -> list[GitHubNotification]:
        """Get notifications.

        Args:
            unread_only: Only return unread notifications
        """
        ...

    async def get_notification_count(self) -> int:
        """Get count of unread notifications."""
        ...

    async def get_prs_to_review(self) -> list[PullRequest]:
        """Get PRs where current user's review is requested."""
        ...

    async def get_recent_workflow_runs(
        self,
        repos: list[str] | None = None,
        limit: int = 10,
    ) -> list[WorkflowRun]:
        """Get recent CI workflow runs.

        Args:
            repos: List of "owner/repo" to check, or None for watched repos
            limit: Max runs to return
        """
        ...

    async def mark_notification_read(self, notification_id: str) -> bool:
        """Mark a notification as read."""
        ...


class GitHubAuthError(Exception):
    """Raised when GitHub authentication fails."""
    pass
```

### Implementation

```python
import asyncio
from github import Github, GithubException
from utils.logger import get_logger

logger = get_logger("github_client")

class GitHubClient:
    def __init__(self, token: str, config: dict[str, Any]) -> None:
        self._token = token
        self._config = config
        self._client: Github | None = None
        self._user: str = ""

    async def initialize(self) -> None:
        # PyGithub is synchronous, wrap in thread
        def _init():
            client = Github(self._token)
            user = client.get_user()
            return client, user.login

        try:
            self._client, self._user = await asyncio.to_thread(_init)
            logger.info(f"GitHub client initialized for user: {self._user}")
        except GithubException as e:
            raise GitHubAuthError(f"Failed to authenticate with GitHub: {e}")

    async def get_notifications(self, unread_only: bool = True) -> list[GitHubNotification]:
        def _get():
            notifications = self._client.get_user().get_notifications(all=not unread_only)
            return [
                GitHubNotification(
                    id=n.id,
                    repo=n.repository.full_name,
                    title=n.subject.title,
                    type=n.subject.type,
                    reason=n.reason,
                    url=n.subject.url,
                    updated_at=n.updated_at,
                    unread=n.unread,
                )
                for n in notifications[:50]  # Limit for performance
            ]

        return await asyncio.to_thread(_get)

    async def get_notification_count(self) -> int:
        notifications = await self.get_notifications(unread_only=True)
        return len(notifications)

    async def get_prs_to_review(self) -> list[PullRequest]:
        def _get():
            # Search for PRs where user's review is requested
            query = f"is:pr is:open review-requested:{self._user}"
            issues = self._client.search_issues(query)

            prs = []
            for issue in issues[:20]:
                pr = issue.as_pull_request()
                prs.append(PullRequest(
                    id=pr.id,
                    repo=pr.base.repo.full_name,
                    number=pr.number,
                    title=pr.title,
                    author=pr.user.login,
                    state=pr.state,
                    draft=pr.draft,
                    review_requested=True,
                    url=pr.html_url,
                    created_at=pr.created_at,
                    updated_at=pr.updated_at,
                ))
            return prs

        return await asyncio.to_thread(_get)

    async def get_recent_workflow_runs(
        self,
        repos: list[str] | None = None,
        limit: int = 10,
    ) -> list[WorkflowRun]:
        def _get():
            watched = repos or self._config.get("watched_repos", [])
            runs = []

            for repo_name in watched[:5]:  # Limit repos for performance
                try:
                    repo = self._client.get_repo(repo_name)
                    for run in repo.get_workflow_runs()[:3]:
                        runs.append(WorkflowRun(
                            id=run.id,
                            repo=repo_name,
                            workflow_name=run.name,
                            branch=run.head_branch,
                            status=run.status,
                            conclusion=run.conclusion,
                            url=run.html_url,
                            created_at=run.created_at,
                        ))
                except GithubException:
                    continue

            # Sort by created_at, most recent first
            runs.sort(key=lambda r: r.created_at, reverse=True)
            return runs[:limit]

        return await asyncio.to_thread(_get)
```

---

## Docker Client (`src/integrations/docker/client.py`)

### Interface

```python
from dataclasses import dataclass
from typing import Any

@dataclass
class ContainerInfo:
    """Docker container information."""
    id: str
    name: str
    image: str
    status: str  # "running", "paused", "exited", etc.
    created: str
    ports: dict[str, list[dict]]  # Port mappings
    cpu_percent: float
    memory_mb: float
    memory_limit_mb: float

class DockerClient:
    """Async Docker client wrapping docker-py."""

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize Docker client.

        Args:
            config: dev_toolkit.docker section from config
        """
        ...

    async def initialize(self) -> None:
        """Connect to Docker daemon."""
        ...

    async def is_available(self) -> bool:
        """Check if Docker daemon is accessible."""
        ...

    async def list_containers(self, all: bool = False) -> list[ContainerInfo]:
        """List containers.

        Args:
            all: Include stopped containers
        """
        ...

    async def get_container_stats(self, container_id: str) -> dict[str, Any]:
        """Get resource stats for a container."""
        ...


class DockerNotAvailableError(Exception):
    """Raised when Docker daemon is not accessible."""
    pass
```

### Implementation

```python
import asyncio
import docker
from docker.errors import DockerException
from utils.logger import get_logger

logger = get_logger("docker_client")

class DockerClient:
    def __init__(self, config: dict[str, Any]) -> None:
        self._config = config
        self._client: docker.DockerClient | None = None

    async def initialize(self) -> None:
        def _init():
            return docker.from_env()

        try:
            self._client = await asyncio.to_thread(_init)
            # Verify connection
            await asyncio.to_thread(self._client.ping)
            logger.info("Docker client initialized")
        except DockerException as e:
            raise DockerNotAvailableError(f"Cannot connect to Docker: {e}")

    async def is_available(self) -> bool:
        if not self._client:
            return False
        try:
            await asyncio.to_thread(self._client.ping)
            return True
        except DockerException:
            return False

    async def list_containers(self, all: bool = False) -> list[ContainerInfo]:
        def _list():
            containers = self._client.containers.list(all=all)
            result = []

            for c in containers:
                # Get stats (non-blocking, one-shot)
                try:
                    stats = c.stats(stream=False)
                    cpu_percent = self._calculate_cpu_percent(stats)
                    memory_mb = stats["memory_stats"].get("usage", 0) / (1024 * 1024)
                    memory_limit = stats["memory_stats"].get("limit", 0) / (1024 * 1024)
                except Exception:
                    cpu_percent = 0.0
                    memory_mb = 0.0
                    memory_limit = 0.0

                result.append(ContainerInfo(
                    id=c.short_id,
                    name=c.name,
                    image=c.image.tags[0] if c.image.tags else c.image.short_id,
                    status=c.status,
                    created=c.attrs["Created"],
                    ports=c.attrs.get("NetworkSettings", {}).get("Ports", {}),
                    cpu_percent=cpu_percent,
                    memory_mb=memory_mb,
                    memory_limit_mb=memory_limit,
                ))

            return result

        return await asyncio.to_thread(_list)

    def _calculate_cpu_percent(self, stats: dict) -> float:
        """Calculate CPU percentage from docker stats."""
        cpu_delta = (
            stats["cpu_stats"]["cpu_usage"]["total_usage"]
            - stats["precpu_stats"]["cpu_usage"]["total_usage"]
        )
        system_delta = (
            stats["cpu_stats"]["system_cpu_usage"]
            - stats["precpu_stats"]["system_cpu_usage"]
        )
        if system_delta > 0:
            cpu_count = len(stats["cpu_stats"]["cpu_usage"].get("percpu_usage", [1]))
            return (cpu_delta / system_delta) * cpu_count * 100.0
        return 0.0
```

---

## Local Repository Watcher

### Interface

```python
from dataclasses import dataclass
from pathlib import Path

@dataclass
class RepoStatus:
    """Local git repository status."""
    path: str
    name: str
    branch: str
    dirty: bool          # Has uncommitted changes
    untracked: int       # Number of untracked files
    ahead: int           # Commits ahead of remote
    behind: int          # Commits behind remote
    last_commit: str     # Short hash + message
    last_activity: float # Timestamp of last file modification

class RepoWatcher:
    """Monitor local git repositories."""

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize with config.

        Args:
            config: dev_toolkit.repo_watcher section
        """
        ...

    async def get_repo_statuses(self) -> list[RepoStatus]:
        """Get status of all watched repositories."""
        ...

    async def get_repo_status(self, path: str) -> RepoStatus | None:
        """Get status of a single repository."""
        ...
```

### Implementation

```python
import asyncio
import subprocess
from pathlib import Path
from utils.logger import get_logger

logger = get_logger("repo_watcher")

class RepoWatcher:
    def __init__(self, config: dict[str, Any]) -> None:
        self._config = config
        self._watched_paths = [
            Path(p).expanduser() for p in config.get("watched_paths", [])
        ]

    async def get_repo_statuses(self) -> list[RepoStatus]:
        statuses = []
        for path in self._watched_paths:
            status = await self.get_repo_status(str(path))
            if status:
                statuses.append(status)
        return statuses

    async def get_repo_status(self, path: str) -> RepoStatus | None:
        repo_path = Path(path)
        if not (repo_path / ".git").exists():
            return None

        async def _run_git(cmd: list[str]) -> str:
            proc = await asyncio.create_subprocess_exec(
                "git", *cmd,
                cwd=repo_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            return stdout.decode().strip()

        try:
            # Current branch
            branch = await _run_git(["rev-parse", "--abbrev-ref", "HEAD"])

            # Dirty status
            status_output = await _run_git(["status", "--porcelain"])
            dirty = bool(status_output)
            untracked = len([l for l in status_output.split("\n") if l.startswith("??")])

            # Ahead/behind
            ahead, behind = 0, 0
            try:
                ab_output = await _run_git([
                    "rev-list", "--left-right", "--count",
                    f"origin/{branch}...HEAD"
                ])
                if ab_output:
                    parts = ab_output.split()
                    if len(parts) == 2:
                        behind, ahead = int(parts[0]), int(parts[1])
            except Exception:
                pass

            # Last commit
            last_commit = await _run_git(["log", "-1", "--oneline"])

            # Last activity (most recent file mtime)
            last_activity = repo_path.stat().st_mtime

            return RepoStatus(
                path=str(repo_path),
                name=repo_path.name,
                branch=branch,
                dirty=dirty,
                untracked=untracked,
                ahead=ahead,
                behind=behind,
                last_commit=last_commit[:50],
                last_activity=last_activity,
            )
        except Exception as e:
            logger.error(f"Failed to get status for {path}: {e}")
            return None
```

---

## Extended System Metrics (`src/integrations/system/metrics.py`)

### Interface

```python
from dataclasses import dataclass

@dataclass
class ExtendedMetrics:
    """Extended system metrics."""
    cpu_percent: float
    memory_percent: float
    memory_used_gb: float
    memory_total_gb: float
    gpu_util: float | None      # NVIDIA GPU utilization %
    gpu_memory_percent: float | None
    gpu_temp: float | None      # Celsius
    cpu_temp: float | None      # Celsius
    network_up_mbps: float      # Upload throughput
    network_down_mbps: float    # Download throughput
    disk_percent: float
    uptime_seconds: int

class SystemMetricsCollector:
    """Collect extended system metrics."""

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize collector.

        Args:
            config: dev_toolkit.system_monitor section
        """
        ...

    async def collect(self) -> ExtendedMetrics:
        """Collect current metrics."""
        ...
```

### Implementation

```python
import asyncio
import psutil
import time
from typing import Any

# Optional GPU support
try:
    import GPUtil
    HAS_GPU = True
except ImportError:
    HAS_GPU = False

class SystemMetricsCollector:
    def __init__(self, config: dict[str, Any]) -> None:
        self._config = config
        self._last_net_io = psutil.net_io_counters()
        self._last_net_time = time.time()
        self._start_time = time.time()

    async def collect(self) -> ExtendedMetrics:
        def _collect():
            # CPU and Memory
            cpu_percent = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory()

            # GPU (if available and configured)
            gpu_util = None
            gpu_mem = None
            gpu_temp = None
            if HAS_GPU and self._config.get("show_gpu", True):
                try:
                    gpus = GPUtil.getGPUs()
                    if gpus:
                        gpu = gpus[0]
                        gpu_util = gpu.load * 100
                        gpu_mem = gpu.memoryUtil * 100
                        gpu_temp = gpu.temperature
                except Exception:
                    pass

            # CPU temperature (Linux)
            cpu_temp = None
            if self._config.get("show_temps", True):
                try:
                    temps = psutil.sensors_temperatures()
                    if "coretemp" in temps:
                        cpu_temp = temps["coretemp"][0].current
                    elif "k10temp" in temps:  # AMD
                        cpu_temp = temps["k10temp"][0].current
                except Exception:
                    pass

            # Network throughput
            current_net = psutil.net_io_counters()
            current_time = time.time()
            time_delta = current_time - self._last_net_time

            if time_delta > 0:
                bytes_sent = current_net.bytes_sent - self._last_net_io.bytes_sent
                bytes_recv = current_net.bytes_recv - self._last_net_io.bytes_recv
                up_mbps = (bytes_sent / time_delta) * 8 / 1_000_000
                down_mbps = (bytes_recv / time_delta) * 8 / 1_000_000
            else:
                up_mbps = 0.0
                down_mbps = 0.0

            self._last_net_io = current_net
            self._last_net_time = current_time

            # Disk
            disk = psutil.disk_usage("/")

            return ExtendedMetrics(
                cpu_percent=cpu_percent,
                memory_percent=mem.percent,
                memory_used_gb=mem.used / (1024**3),
                memory_total_gb=mem.total / (1024**3),
                gpu_util=gpu_util,
                gpu_memory_percent=gpu_mem,
                gpu_temp=gpu_temp,
                cpu_temp=cpu_temp,
                network_up_mbps=up_mbps,
                network_down_mbps=down_mbps,
                disk_percent=disk.percent,
                uptime_seconds=int(current_time - self._start_time),
            )

        return await asyncio.to_thread(_collect)
```

---

## DevToolkit Agent (`src/brain/agents/dev_toolkit_agent.py`)

### Interface

```python
from brain.agents.base import BaseAgent, AgentResult

class DevToolkitAgent(BaseAgent):
    """Agent for developer toolkit queries."""

    def __init__(
        self,
        github_client: GitHubClient | None,
        docker_client: DockerClient | None,
        repo_watcher: RepoWatcher | None,
    ) -> None:
        ...

    async def run(
        self,
        task: str,
        params: dict[str, Any],
        language: str,
    ) -> AgentResult:
        """Handle dev toolkit query.

        Args:
            task: User query
            params: Parsed parameters
            language: Response language
        """
        ...
```

### Action Handlers

```python
async def run(self, task: str, params: dict, language: str) -> AgentResult:
    action = params.get("action", "status")

    if action == "github_notifications":
        return await self._handle_notifications(language)
    elif action == "prs_to_review":
        return await self._handle_prs(language)
    elif action == "repo_status":
        return await self._handle_repos(language)
    elif action == "docker_status":
        return await self._handle_docker(language)
    elif action == "ci_status":
        return await self._handle_ci(params, language)
    else:
        # General status overview
        return await self._handle_overview(language)

async def _handle_notifications(self, language: str) -> AgentResult:
    if not self._github:
        return self._no_github_response(language)

    count = await self._github.get_notification_count()
    if count == 0:
        msg = "No unread GitHub notifications." if language == "en" else "Keine ungelesenen GitHub-Benachrichtigungen."
    else:
        msg = f"You have {count} unread GitHub notifications." if language == "en" else f"Sie haben {count} ungelesene GitHub-Benachrichtigungen."

    return AgentResult(spoken_response=msg, success=True)

async def _handle_prs(self, language: str) -> AgentResult:
    if not self._github:
        return self._no_github_response(language)

    prs = await self._github.get_prs_to_review()
    if not prs:
        msg = "No pull requests awaiting your review." if language == "en" else "Keine Pull Requests warten auf Ihre Review."
    else:
        count = len(prs)
        first_pr = prs[0]
        if language == "de":
            msg = f"Sie haben {count} Pull Requests zu reviewen. Der erste ist '{first_pr.title}' von {first_pr.author}."
        else:
            msg = f"You have {count} pull requests to review. The first is '{first_pr.title}' by {first_pr.author}."

    return AgentResult(spoken_response=msg, success=True, data={"prs": [p.__dict__ for p in prs]})

async def _handle_repos(self, language: str) -> AgentResult:
    if not self._repo_watcher:
        return AgentResult(spoken_response="Repository watcher not configured.", success=False)

    statuses = await self._repo_watcher.get_repo_statuses()
    dirty_repos = [s for s in statuses if s.dirty]

    if not dirty_repos:
        msg = "All watched repositories are clean." if language == "en" else "Alle überwachten Repositories sind sauber."
    else:
        names = ", ".join(s.name for s in dirty_repos[:3])
        if language == "de":
            msg = f"Sie haben uncommittete Änderungen in: {names}."
        else:
            msg = f"You have uncommitted changes in: {names}."

    return AgentResult(spoken_response=msg, success=True, data={"repos": [s.__dict__ for s in statuses]})

async def _handle_docker(self, language: str) -> AgentResult:
    if not self._docker or not await self._docker.is_available():
        msg = "Docker is not available." if language == "en" else "Docker ist nicht verfügbar."
        return AgentResult(spoken_response=msg, success=False)

    containers = await self._docker.list_containers()
    running = [c for c in containers if c.status == "running"]

    if not running:
        msg = "No Docker containers are running." if language == "en" else "Keine Docker-Container laufen."
    else:
        count = len(running)
        names = ", ".join(c.name for c in running[:3])
        if language == "de":
            msg = f"{count} Container laufen: {names}."
        else:
            msg = f"{count} containers running: {names}."

    return AgentResult(spoken_response=msg, success=True, data={"containers": [c.__dict__ for c in containers]})

async def _handle_ci(self, params: dict, language: str) -> AgentResult:
    if not self._github:
        return self._no_github_response(language)

    repo = params.get("repo")
    runs = await self._github.get_recent_workflow_runs(
        repos=[repo] if repo else None,
        limit=5,
    )

    if not runs:
        msg = "No recent CI builds found." if language == "en" else "Keine aktuellen CI-Builds gefunden."
    else:
        latest = runs[0]
        status = latest.conclusion or latest.status
        if language == "de":
            msg = f"Der letzte Build für {latest.repo} ist {status}."
        else:
            msg = f"The latest build for {latest.repo} is {status}."

    return AgentResult(spoken_response=msg, success=True, data={"builds": [r.__dict__ for r in runs]})
```

---

## Intent Parser Updates

Add to `src/brain/intent_parser.py`:

```python
class Intent(Enum):
    # ... existing ...
    DEV_TOOLKIT = "dev_toolkit"

INTENT_KEYWORDS[Intent.DEV_TOOLKIT] = {
    "en": [
        r"\bgithub\s+(notifications?|alerts?)\b",
        r"\bpull\s+requests?\s+(to\s+)?review\b",
        r"\bprs?\s+to\s+review\b",
        r"\brepo(sitor(y|ies))?\s+status\b",
        r"\bhow\s+are\s+my\s+repos?\b",
        r"\buncommitted\s+changes?\b",
        r"\bdirty\s+repos?\b",
        r"\bdocker\s+(containers?|status)\b",
        r"\bwhat\s+(containers?|is)\s+running\b",
        r"\bshow\s+containers?\b",
        r"\bci\s+(status|build|pipeline)\b",
        r"\bbuild\s+status\b",
        r"\bgithub\s+actions?\b",
        r"\bworkflow\s+(status|runs?)\b",
    ],
    "de": [
        r"\bgithub\s+(benachrichtigungen?|meldungen?)\b",
        r"\bpull\s+requests?\s+(zu\s+)?reviewen\b",
        r"\bprs?\s+(zu\s+)?reviewen\b",
        r"\brepo(sitor(y|ies))?\s+status\b",
        r"\bwie\s+(sind|stehen)\s+(meine\s+)?repos?\b",
        r"\buncommittete?\s+änderungen?\b",
        r"\bdocker\s+(container|status)\b",
        r"\bwelche\s+container\s+laufen\b",
        r"\bzeig(e)?\s+container\b",
        r"\bci\s+(status|build|pipeline)\b",
        r"\bbuild\s+status\b",
    ],
}
```

### Parameter Extraction

```python
def _extract_dev_toolkit_params(self, text: str) -> dict[str, Any]:
    params: dict[str, Any] = {"action": "overview"}

    if re.search(r"\b(notification|alert|benachrichtigung|meldung)\b", text):
        params["action"] = "github_notifications"
    elif re.search(r"\b(pull\s+request|pr|review)\b", text):
        params["action"] = "prs_to_review"
    elif re.search(r"\b(repo|uncommitted|dirty)\b", text):
        params["action"] = "repo_status"
    elif re.search(r"\b(docker|container)\b", text):
        params["action"] = "docker_status"
    elif re.search(r"\b(ci|build|workflow|pipeline|actions?)\b", text):
        params["action"] = "ci_status"
        # Extract repo name if mentioned
        match = re.search(r"\b([\w-]+/[\w-]+)\b", text)
        if match:
            params["repo"] = match.group(1)

    return params
```

---

## State Broadcast Loop

Update `src/api/ws_server.py`:

```python
async def _dev_toolkit_state_loop() -> None:
    """Background task to broadcast dev toolkit state."""
    poll_interval = 30  # seconds

    while True:
        try:
            payload = {
                "github": {
                    "notifications": 0,
                    "prs_to_review": 0,
                },
                "repos": [],
                "docker": [],
                "ci": [],
            }

            # GitHub
            if _github_client:
                payload["github"]["notifications"] = await _github_client.get_notification_count()
                prs = await _github_client.get_prs_to_review()
                payload["github"]["prs_to_review"] = len(prs)

                # CI
                runs = await _github_client.get_recent_workflow_runs(limit=5)
                payload["ci"] = [
                    {
                        "repo": r.repo,
                        "workflow": r.workflow_name,
                        "status": r.conclusion or r.status,
                        "url": r.url,
                    }
                    for r in runs
                ]

            # Repos
            if _repo_watcher:
                statuses = await _repo_watcher.get_repo_statuses()
                payload["repos"] = [
                    {
                        "path": s.path,
                        "branch": s.branch,
                        "dirty": s.dirty,
                        "ahead": s.ahead,
                        "behind": s.behind,
                    }
                    for s in statuses
                ]

            # Docker
            if _docker_client and await _docker_client.is_available():
                containers = await _docker_client.list_containers()
                payload["docker"] = [
                    {
                        "id": c.id,
                        "name": c.name,
                        "status": c.status,
                        "cpu": round(c.cpu_percent, 1),
                        "mem": round(c.memory_mb, 1),
                    }
                    for c in containers
                ]

            await _broadcast(json.dumps({
                "type": "dev_toolkit",
                "payload": payload,
            }))
        except Exception as e:
            logger.error(f"Error polling dev toolkit state: {e}")

        await asyncio.sleep(poll_interval)


async def _extended_system_metrics_loop() -> None:
    """Enhanced system metrics with GPU, temps, network."""
    poll_interval = 5

    while True:
        try:
            if _metrics_collector:
                metrics = await _metrics_collector.collect()
                payload = {
                    "cpu": metrics.cpu_percent,
                    "mem": metrics.memory_percent,
                    "uptime": _format_uptime(metrics.uptime_seconds),
                    "gpu_util": metrics.gpu_util,
                    "gpu_temp": metrics.gpu_temp,
                    "cpu_temp": metrics.cpu_temp,
                    "network_up": round(metrics.network_up_mbps, 2),
                    "network_down": round(metrics.network_down_mbps, 2),
                }
                await _broadcast(json.dumps({
                    "type": "system",
                    "payload": payload,
                }))
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")

        await asyncio.sleep(poll_interval)
```

---

## DevPanel (`frontend/src/components/panels/DevPanel.tsx`)

```typescript
import { PanelBase } from './PanelBase';
import { useDevToolkit } from '../../hooks/useDevToolkit';

export function DevPanel() {
  const { state, loading, error } = useDevToolkit();

  return (
    <PanelBase title="DEVELOPER" icon={<CodeIcon />} loading={loading} error={error}>
      {/* GitHub section */}
      <Section title="GITHUB">
        <StatRow label="Notifications" value={state?.github.notifications ?? 0} />
        <StatRow
          label="PRs to Review"
          value={state?.github.prs_to_review ?? 0}
          highlight={state?.github.prs_to_review > 0}
        />
      </Section>

      {/* Repositories section */}
      {state?.repos.length > 0 && (
        <Section title="REPOSITORIES">
          {state.repos.map((repo) => (
            <RepoRow key={repo.path} repo={repo} />
          ))}
        </Section>
      )}

      {/* Docker section */}
      {state?.docker.length > 0 && (
        <Section title="DOCKER">
          {state.docker.map((container) => (
            <ContainerRow key={container.id} container={container} />
          ))}
        </Section>
      )}

      {/* CI section */}
      {state?.ci.length > 0 && (
        <Section title="CI BUILDS">
          {state.ci.slice(0, 3).map((build) => (
            <BuildRow key={`${build.repo}-${build.workflow}`} build={build} />
          ))}
        </Section>
      )}
    </PanelBase>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: '16px' }}>
      <div
        style={{
          fontSize: '9px',
          color: 'var(--text-muted)',
          letterSpacing: '1px',
          marginBottom: '8px',
        }}
      >
        {title}
      </div>
      {children}
    </div>
  );
}

function StatRow({ label, value, highlight }: { label: string; value: number; highlight?: boolean }) {
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        fontSize: '12px',
        padding: '4px 0',
      }}
    >
      <span style={{ color: 'var(--text-secondary)' }}>{label}</span>
      <span
        style={{
          color: highlight ? 'var(--warning)' : 'var(--text)',
          fontWeight: highlight ? 600 : 400,
        }}
      >
        {value}
      </span>
    </div>
  );
}

function RepoRow({ repo }: { repo: RepoStatus }) {
  const statusColor = repo.dirty ? 'var(--warning)' : 'var(--success)';
  const statusText = repo.dirty ? 'dirty' : 'clean';

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        fontSize: '11px',
        padding: '4px 0',
      }}
    >
      <span
        style={{
          width: '6px',
          height: '6px',
          borderRadius: '3px',
          background: statusColor,
        }}
      />
      <span style={{ flex: 1, color: 'var(--text)' }}>{repo.path.split('/').pop()}</span>
      <span style={{ color: 'var(--text-muted)' }}>{repo.branch}</span>
      <span style={{ color: statusColor, fontSize: '10px' }}>{statusText}</span>
    </div>
  );
}

function ContainerRow({ container }: { container: DockerContainer }) {
  const statusColor = container.status === 'running' ? 'var(--success)' : 'var(--text-muted)';

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        fontSize: '11px',
        padding: '4px 0',
      }}
    >
      <span
        style={{
          width: '6px',
          height: '6px',
          borderRadius: '3px',
          background: statusColor,
        }}
      />
      <span style={{ flex: 1, color: 'var(--text)' }}>{container.name}</span>
      <span style={{ color: 'var(--text-muted)' }}>
        {container.cpu.toFixed(1)}% / {container.mem.toFixed(0)}MB
      </span>
    </div>
  );
}

function BuildRow({ build }: { build: CIBuild }) {
  const statusColors: Record<string, string> = {
    success: 'var(--success)',
    failure: 'var(--danger)',
    pending: 'var(--warning)',
    running: 'var(--info)',
  };

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        fontSize: '11px',
        padding: '4px 0',
      }}
    >
      <span
        style={{
          width: '6px',
          height: '6px',
          borderRadius: '3px',
          background: statusColors[build.status] || 'var(--text-muted)',
        }}
      />
      <span style={{ flex: 1, color: 'var(--text)' }}>
        {build.repo.split('/').pop()}
      </span>
      <span style={{ color: 'var(--text-muted)', fontSize: '10px' }}>
        {build.workflow}
      </span>
    </div>
  );
}

function CodeIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="16,18 22,12 16,6" />
      <polyline points="8,6 2,12 8,18" />
    </svg>
  );
}

export default DevPanel;
```

---

## Updated SystemPanel (`frontend/src/components/panels/SystemPanel.tsx`)

```typescript
import { PanelBase } from './PanelBase';
import { useSystemMetrics } from '../../hooks/useSystemMetrics';

export function SystemPanel() {
  const { metrics, loading, error } = useSystemMetrics();

  return (
    <PanelBase title="SYSTEM" icon={<CpuIcon />} loading={loading} error={error}>
      {/* CPU */}
      <MetricBar label="CPU" value={metrics?.cpu ?? 0} unit="%" />

      {/* Memory */}
      <MetricBar label="MEM" value={metrics?.mem ?? 0} unit="%" />

      {/* GPU (if available) */}
      {metrics?.gpu_util != null && (
        <MetricBar label="GPU" value={metrics.gpu_util} unit="%" />
      )}

      {/* Temperatures */}
      <div style={{ display: 'flex', gap: '16px', marginTop: '12px' }}>
        {metrics?.cpu_temp != null && (
          <TempDisplay label="CPU" value={metrics.cpu_temp} />
        )}
        {metrics?.gpu_temp != null && (
          <TempDisplay label="GPU" value={metrics.gpu_temp} />
        )}
      </div>

      {/* Network */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          marginTop: '12px',
          fontSize: '10px',
          color: 'var(--text-muted)',
        }}
      >
        <span>UP {metrics?.network_up?.toFixed(1) ?? 0} Mbps</span>
        <span>DOWN {metrics?.network_down?.toFixed(1) ?? 0} Mbps</span>
      </div>

      {/* Uptime */}
      <div
        style={{
          marginTop: '12px',
          fontSize: '10px',
          color: 'var(--text-muted)',
          textAlign: 'center',
        }}
      >
        UPTIME {metrics?.uptime ?? '--'}
      </div>
    </PanelBase>
  );
}

function MetricBar({ label, value, unit }: { label: string; value: number; unit: string }) {
  const color = value > 80 ? 'var(--danger)' : value > 60 ? 'var(--warning)' : 'var(--accent)';

  return (
    <div style={{ marginBottom: '8px' }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          fontSize: '10px',
          marginBottom: '4px',
        }}
      >
        <span style={{ color: 'var(--text-muted)' }}>{label}</span>
        <span style={{ color: 'var(--text)' }}>{value.toFixed(0)}{unit}</span>
      </div>
      <div
        style={{
          height: '4px',
          background: 'var(--panel-border)',
          borderRadius: '2px',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            width: `${Math.min(100, value)}%`,
            height: '100%',
            background: color,
            transition: 'width 300ms',
          }}
        />
      </div>
    </div>
  );
}

function TempDisplay({ label, value }: { label: string; value: number }) {
  const color = value > 80 ? 'var(--danger)' : value > 70 ? 'var(--warning)' : 'var(--text)';

  return (
    <div style={{ textAlign: 'center' }}>
      <div style={{ fontSize: '16px', fontWeight: 500, color }}>{value.toFixed(0)}</div>
      <div style={{ fontSize: '9px', color: 'var(--text-muted)' }}>{label}</div>
    </div>
  );
}

function CpuIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="4" y="4" width="16" height="16" rx="2" />
      <rect x="9" y="9" width="6" height="6" />
      <line x1="9" y1="1" x2="9" y2="4" />
      <line x1="15" y1="1" x2="15" y2="4" />
      <line x1="9" y1="20" x2="9" y2="23" />
      <line x1="15" y1="20" x2="15" y2="23" />
      <line x1="20" y1="9" x2="23" y2="9" />
      <line x1="20" y1="14" x2="23" y2="14" />
      <line x1="1" y1="9" x2="4" y2="9" />
      <line x1="1" y1="14" x2="4" y2="14" />
    </svg>
  );
}

export default SystemPanel;
```

---

## Configuration

### config.yaml

```yaml
dev_toolkit:
  enabled: true

  github:
    enabled: false              # Requires GITHUB_TOKEN
    poll_interval_seconds: 60
    watched_repos: []           # ["owner/repo", ...] empty = use notifications API

  repo_watcher:
    enabled: true
    poll_interval_seconds: 30
    watched_paths:              # Local paths to monitor
      - "~/Projects/my-project"
      - "~/Repos/Jarvis"

  docker:
    enabled: true
    poll_interval_seconds: 15

  system_monitor:
    enabled: true
    poll_interval_seconds: 5
    show_gpu: true              # Requires GPUtil
    show_network: true
    show_temps: true            # Linux only (psutil.sensors_temperatures)
```

### .env.example

```bash
# GitHub Personal Access Token
# Scopes: notifications, repo, read:user
GITHUB_TOKEN=ghp_your_token_here
```

---

## Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | GitHubClient initializes with valid PAT | Unit test |
| 2 | "Any GitHub notifications?" returns count | Integration test |
| 3 | "Any PRs to review?" lists pending reviews | Integration test |
| 4 | "How are my repos?" reports dirty/clean status | Integration test |
| 5 | "Show containers" lists running Docker containers | Integration test |
| 6 | "Build status for X" reports CI status | Integration test |
| 7 | DevPanel displays GitHub notification count | Visual inspection |
| 8 | DevPanel shows repo dirty indicators | Visual inspection |
| 9 | DevPanel shows Docker container list | Visual inspection |
| 10 | DevPanel shows CI build status with colors | Visual inspection |
| 11 | SystemPanel shows GPU utilization (if available) | Visual inspection |
| 12 | SystemPanel shows CPU/GPU temperatures | Visual inspection |
| 13 | SystemPanel shows network throughput | Visual inspection |
| 14 | German voice commands work | Integration test |
| 15 | dev_toolkit WS message broadcasts correctly | Unit test |
| 16 | No crash when GitHub token missing | Integration test |
| 17 | No crash when Docker unavailable | Integration test |
| 18 | Repo watcher handles missing .git directories | Unit test |

---

## Files Created

| File | Purpose |
|------|---------|
| `src/integrations/github/__init__.py` | Package init |
| `src/integrations/github/client.py` | GitHubClient |
| `src/integrations/docker/__init__.py` | Package init |
| `src/integrations/docker/client.py` | DockerClient |
| `src/integrations/system/__init__.py` | Package init |
| `src/integrations/system/metrics.py` | SystemMetricsCollector + RepoWatcher |
| `src/brain/agents/dev_toolkit_agent.py` | DevToolkitAgent |
| `frontend/src/components/panels/DevPanel.tsx` | Dev toolkit panel |
| `frontend/src/hooks/useDevToolkit.ts` | Dev toolkit hook |
| `tests/integrations/github/test_client.py` | GitHub tests |
| `tests/integrations/docker/test_client.py` | Docker tests |
| `tests/brain/agents/test_dev_toolkit_agent.py` | Agent tests |

## Files Modified

| File | Change |
|------|--------|
| `src/brain/intent_parser.py` | Add DEV_TOOLKIT intent |
| `src/brain/orchestrator.py` | Register DevToolkitAgent |
| `src/api/ws_server.py` | Add dev_toolkit and extended system loops |
| `src/main.py` | Initialize all dev toolkit clients |
| `frontend/src/components/panels/SystemPanel.tsx` | Extend with GPU/temps/network |
| `frontend/src/hooks/useSystemMetrics.ts` | Handle extended metrics |
| `config/config.yaml` | Add dev_toolkit section |
| `.env.example` | Add GITHUB_TOKEN |
| `requirements.txt` | Add PyGithub, docker, GPUtil |

---

## Dependencies

### pip packages
```
PyGithub>=2.1.0
docker>=6.1.0
GPUtil>=1.4.0        # Optional, for NVIDIA GPU metrics
```

---

## Implementation Plan

### Batch 1 — GitHub client
1. `code` → Create `src/integrations/github/__init__.py`
2. `code` → Create `src/integrations/github/client.py`
3. `test` → Create `tests/integrations/github/test_client.py`
4. `review` → Review batch 1

### Batch 2 — Docker client
5. `code` → Create `src/integrations/docker/__init__.py`
6. `code` → Create `src/integrations/docker/client.py`
7. `test` → Create `tests/integrations/docker/test_client.py`
8. `review` → Review batch 2

### Batch 3 — System metrics and repo watcher
9. `code` → Create `src/integrations/system/metrics.py` (both classes)
10. `test` → Create tests for SystemMetricsCollector and RepoWatcher
11. `review` → Review batch 3

### Batch 4 — Agent and intents
12. `code` → Update `src/brain/intent_parser.py`
13. `code` → Create `src/brain/agents/dev_toolkit_agent.py`
14. `code` → Update `src/brain/orchestrator.py`
15. `test` → Create `tests/brain/agents/test_dev_toolkit_agent.py`
16. `review` → Review batch 4

### Batch 5 — WS integration
17. `code` → Update `src/api/ws_server.py` with broadcast loops
18. `code` → Update `src/main.py` with initialization
19. `test` → Integration tests
20. `review` → Review batch 5

### Batch 6 — Frontend
21. `design` → Create `frontend/src/hooks/useDevToolkit.ts`
22. `design` → Create `frontend/src/components/panels/DevPanel.tsx`
23. `design` → Update `frontend/src/components/panels/SystemPanel.tsx`
24. `test` → Frontend tests
25. `review` → Final review

---

## Open Questions — ALL RESOLVED

1. **Dev-toolkit scope for MVP:** ✓ RESOLVED — See Revision 2 for explicit MVP/Phase B split

2. **SE-specific enhancements:** ✓ RESOLVED — Deferred to Phase B; MVP remains generic

---

## Out of Scope (Phase B)

The following features are explicitly deferred to Phase B. They will NOT be part of the MVP release:

| Feature | Reason for Deferral |
|---------|---------------------|
| **NPM / pip CVE scans** | Too noisy without proper severity thresholds and ignore lists |
| **Jira/Linear integration** | Requires additional OAuth and API complexity |
| **Language-server diagnostics** | Requires running LSP servers; heavy for HUD context |
| **Real-time build-log streaming** | WebSocket complexity for log tailing |

These items are tracked for future implementation in Phase B.

---

## Revision 2 — 2026-04-16

### Summary of Changes
This revision clarifies MVP scope with explicit in-scope and out-of-scope lists.

### MVP Scope — CONFIRMED

**All of the following are IN SCOPE for MVP:**

| Feature | Description |
|---------|-------------|
| GitHub notifications | Unread notification count |
| PR review counter | PRs awaiting user's review |
| Review requests | PRs where user is requested reviewer |
| Local repo watcher | Configurable paths, dirty/ahead/behind status |
| Docker container status | Read-only list + per-container CPU/mem |
| GitHub Actions CI status | Latest run per watched repo |
| Extended system monitor | CPU, RAM, GPU (via `GPUtil`), CPU/GPU temp (via `psutil` sensors or `lm-sensors`), network I/O, disk usage |

### Goals — Updated
Update Goals section to reflect confirmed MVP scope:
- Display GitHub notification count, PR review count, and review requests
- Monitor local git repositories for dirty/ahead/behind status (configurable paths)
- Show running Docker containers with CPU/mem usage (read-only)
- Display GitHub Actions CI build status for watched repos
- Extended system metrics: CPU, RAM, GPU utilization, CPU/GPU temps, network I/O, disk usage
- Enable voice queries: "how are my repos", "any PRs to review", "show containers"

### Non-Goals — Updated
Add explicit Phase B items:
- GitHub issue management (create/close issues)
- Docker container creation/deletion (read-only monitoring only)
- CI trigger/restart from JARVIS
- Kubernetes/cloud container orchestration
- IDE integration or code editing
- **NPM / pip CVE scans** (Phase B)
- **Jira/Linear integration** (Phase B)
- **Language-server diagnostics** (Phase B)
- **Real-time build-log streaming** (Phase B)

---

**Status:** Planned — awaiting implementation authorization

---

## Revision 3 — Full OpenClaw Adoption (2026-04-16)

### Decisions Applied
1. **OpenClaw as full backbone WHERE IT HAS COVERAGE** — GitHub via OpenClaw
2. **JARVIS-native for local operations** — Docker, repos, system metrics stay native

### Integration Assessment
**PARTIALLY replaceable — GitHub via OpenClaw, local monitoring stays JARVIS-native.**

### OpenClaw Coverage
| Feature | OpenClaw Capability | Coverage |
|---------|---------------------|----------|
| GitHub notifications | GitHub skill | Full |
| GitHub PRs to review | GitHub skill | Full |
| GitHub Actions CI status | GitHub skill | Full |
| Local repo watcher | No equivalent | None |
| Docker container status | No equivalent | None |
| Extended system metrics | No equivalent | None |

### What OpenClaw Replaces
- ~~GitHubClient~~ — REMOVED (OpenClaw handles)
- ~~GitHub polling loop~~ — REMOVED (OpenClaw handles)
- ~~GITHUB_TOKEN in .env~~ — REMOVED (OpenClaw handles auth)

### What JARVIS-Native Retains
- **RepoWatcher** — Local git repository monitoring
- **DockerClient** — Local container monitoring via docker-py
- **SystemMetricsCollector** — psutil + GPUtil for local system metrics
- **DevPanel** — HUD panel rendering all dev toolkit state
- **SystemPanel** — Extended metrics visualization (CPU/GPU/temps/network)

### Two-Layer Architecture
```
Layer 1 (OpenClaw): GitHub operations
  Voice: "Any PRs to review?"
         ↓
  [Orchestrator] → Forward to OpenClaw
         ↓
  [OpenClaw GitHub skill] → Returns PR data
         ↓
  [DevPanel] → Display PR count

Layer 2 (JARVIS-native): Local operations
  [RepoWatcher] → Poll local git repos
  [DockerClient] → Poll docker containers
  [SystemMetricsCollector] → Collect CPU/GPU/temps
         ↓
  [WS broadcast] → dev_toolkit + system messages
         ↓
  [DevPanel/SystemPanel] → Display state
```

### Files Created — REDUCED
| File | Purpose | Status |
|------|---------|--------|
| `src/integrations/github/__init__.py` | Package init | SKIP (OpenClaw) |
| `src/integrations/github/client.py` | GitHubClient | SKIP (OpenClaw) |
| `src/integrations/docker/__init__.py` | Package init | KEEP |
| `src/integrations/docker/client.py` | DockerClient | KEEP |
| `src/integrations/system/metrics.py` | SystemMetricsCollector + RepoWatcher | KEEP |
| `src/brain/agents/dev_toolkit_agent.py` | DevToolkitAgent (local only) | KEEP (simplified) |
| `frontend/src/components/panels/DevPanel.tsx` | Dev toolkit panel | KEEP |
| `frontend/src/hooks/useDevToolkit.ts` | Dev toolkit hook | KEEP |

### Files Modified — REDUCED
| File | Change | Status |
|------|--------|--------|
| `src/brain/intent_parser.py` | DEV_TOOLKIT intent | KEEP |
| `src/brain/orchestrator.py` | Route GitHub to OpenClaw, local to DevToolkitAgent | MODIFIED |
| `src/api/ws_server.py` | Local-only dev_toolkit_state_loop | SIMPLIFIED |
| `config/config.yaml` | dev_toolkit section | SIMPLIFIED |

### Config — Simplified
```yaml
dev_toolkit:
  enabled: true
  
  github:
    enabled: true
    provider: "openclaw"  # Always OpenClaw
  
  repo_watcher:
    enabled: true
    poll_interval_seconds: 30
    watched_paths:
      - "~/Repos/Jarvis"
  
  docker:
    enabled: true
    poll_interval_seconds: 15
  
  system_monitor:
    enabled: true
    poll_interval_seconds: 5
    show_gpu: true
    show_temps: true
```

### Implementation Reduction
**Original estimate:** 10-14 hours
**With OpenClaw:** 6-8 hours (no GitHub client, simplified routing)
**Reduction:** ~40%

### Prerequisites
- `openclaw-integration.md` — REQUIRED (for GitHub operations)

### Cross-References
- `hud-panel-framework.md` — DevPanel, SystemPanel integration
