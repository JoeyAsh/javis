# Feature: GitHub DevPanel Live-Wiring

## Status
Planned — awaiting implementation authorization

## Goal
Replace the static mock data in `DevPanel.tsx` with live GitHub data polled from the
authenticated user's account. The panel must show open PRs (assigned to or authored by the
authenticated user), open issues assigned to the user, and the latest GitHub Actions CI run
per configured repo — all refreshing automatically every 30–60 s without any user action.

## Scope
### In scope
- Backend async GitHub client at `src/integrations/github/client.py` (raw `aiohttp`, see
  Architecture rationale).
- Background polling task that runs on the configured interval and caches the last-known
  state in memory.
- New WS message type `github_state` broadcast to all connected clients on each poll tick
  and immediately on first client connect.
- `config.yaml` `github:` section: `enabled`, `poll_interval_seconds`, `repos` (explicit
  list of `"owner/repo"` strings).
- `GITHUB_TOKEN` read from `.env` — no OAuth flow, classic PAT only.
- `DevPanel.tsx` wired to consume `github_state` via a new `useGitHubState` hook; mock
  fallback retained for `GITHUB_TOKEN` absent / feature disabled.
- New TypeScript types for the live payload in `frontend/src/types.ts`.
- Unit + integration tests for the backend client (mocked HTTP) and the frontend hook.

### Out of scope
- Voice intents ("Jarvis, wie ist der Status meiner PRs") — deferred to Phase B.
- GitHub webhooks — polling only for this batch.
- GitHub issue create/close actions.
- Local repo status watcher (`git` process monitoring) — separate feature.
- Docker container section of DevPanel — untouched.
- Pagination beyond the first page of results from each endpoint (20-item cap is fine for
  the HUD context).
- GraphQL GitHub API — REST v3 only.

## User Flow
1. JARVIS backend starts; `GitHubPoller` reads `github.enabled` and `GITHUB_TOKEN` from
   config / env. If disabled or token absent, the poller does not start and the panel
   renders mock data.
2. Poller fires immediately on first connected client, then every `poll_interval_seconds`.
3. Each poll fetches PRs (open, involving authenticated user), assigned open issues, and
   latest CI run for each repo in `github.repos`.
4. Backend broadcasts `{ "type": "github_state", "payload": GitHubStatePayload }` over WS
   to all connected clients.
5. `DevPanel` (expanded mode) shows: PR list with title, repo, author, age; issue list with
   title, repo, age; CI badges per repo (latest run status + age).
6. `DevPanel` (compact mode) shows: open PR count, open issue count, CI badge for the first
   failing or running repo (or "all green" indicator).
7. If a poll fails (network error, rate limit, expired token), the panel retains the last
   successful payload and renders a subtle stale-data indicator (`[stale]` tag in the
   section header).

## Architecture

### Modules touched
- Backend:
  - `src/integrations/github/__init__.py` (new — package init, exports `GitHubClient`,
    `GitHubPoller`)
  - `src/integrations/github/client.py` (new — async GitHub REST client)
  - `src/integrations/github/poller.py` (new — background polling task, caches state)
  - `src/api/ws_server.py` (extend: start/stop poller, broadcast `github_state`)
- Frontend:
  - `frontend/src/hooks/useGitHubState.ts` (new — subscribes to `github_state` WS msgs)
  - `frontend/src/components/panels/DevPanel.tsx` (modify — accept live data from hook)
  - `frontend/src/types.ts` (modify — add `GitHubStatePayload`, extend `WsIncoming`)
- Config:
  - `config/config.yaml` — new top-level `github:` key (see Interfaces)
- Env:
  - `.env` — `GITHUB_TOKEN=ghp_...` (classic PAT, scopes: `repo` read, `read:org`)

### Data flow

```
[GitHub REST API v3]
        │  aiohttp (async GET, per-endpoint)
        ▼
src/integrations/github/client.py
  GitHubClient.fetch_my_prs()
  GitHubClient.fetch_my_issues()
  GitHubClient.fetch_ci_status(repo)  ← one call per repo in config list
        │
        ▼
src/integrations/github/poller.py
  GitHubPoller._poll()  ← asyncio.sleep(poll_interval_seconds) loop
  GitHubPoller.last_state: GitHubStatePayload | None  ← in-memory cache
        │  broadcast via _connected_clients set (already in ws_server.py)
        ▼
src/api/ws_server.py
  broadcast_github_state(payload)
        │  WS JSON frame: { type: "github_state", payload: {...} }
        ▼
frontend/src/hooks/useGitHubState.ts
  subscribeGitHubState(listener)  ← fan-out pattern matching useWebSocket.ts
        │
        ▼
frontend/src/components/panels/DevPanel.tsx
  DevExpanded / DevCompact — render live tiles
```

**Client library rationale — raw `aiohttp` over `PyGithub`:**
`PyGithub` is synchronous and wraps responses in heavy object graphs unsuitable for
asyncio. Running it in `asyncio.to_thread` adds unnecessary thread-pool overhead for a
simple polling use case. The GitHub REST v3 endpoints needed here (search PRs, list
issues, list workflow runs) are simple JSON GETs that map directly to `aiohttp` with no
wrapper needed. This avoids a new dependency with a blocking I/O model.

### Interfaces

**Python — `src/integrations/github/client.py`**

```
@dataclass
class GithubPR:
    id: str
    repo: str
    title: str
    author: str
    html_url: str
    updated_at: str   # ISO

@dataclass
class GithubIssue:
    id: str
    repo: str
    title: str
    html_url: str
    updated_at: str   # ISO

@dataclass
class GithubCIRun:
    repo: str
    status: Literal["success", "failure", "running", "pending"]
    ran_at: str        # ISO
    html_url: str

@dataclass
class GitHubStatePayload:
    prs: list[GithubPR]
    issues: list[GithubIssue]
    ci: list[GithubCIRun]
    fetched_at: str    # ISO
    stale: bool        # True if last poll failed; data is from previous tick

class GitHubClient:
    def __init__(self, token: str, session: aiohttp.ClientSession) -> None: ...
    async def fetch_my_prs(self) -> list[GithubPR]: ...
    async def fetch_my_issues(self) -> list[GithubIssue]: ...
    async def fetch_ci_status(self, repo: str) -> GithubCIRun | None: ...

class GitHubAuthError(Exception): ...
class GitHubRateLimitError(Exception): ...
```

**Python — `src/integrations/github/poller.py`**

```
class GitHubPoller:
    def __init__(
        self,
        client: GitHubClient,
        repos: list[str],
        poll_interval: int,
        broadcast_fn: Callable[[GitHubStatePayload], Awaitable[None]],
    ) -> None: ...
    async def start(self) -> None: ...   # spawns asyncio.Task
    async def stop(self) -> None: ...
    @property
    def last_state(self) -> GitHubStatePayload | None: ...
```

**WS message — new `github_state` variant (server → client)**

```typescript
// Added to WsIncoming union in frontend/src/types.ts
| { type: 'github_state'; payload: GitHubStatePayload }

interface GitHubStatePayload {
  prs: GithubPRLive[];
  issues: GithubIssueLive[];
  ci: GithubCIRunLive[];
  fetched_at: string;   // ISO
  stale: boolean;
}

interface GithubPRLive {
  id: string;
  repo: string;
  title: string;
  author: string;
  html_url: string;
  updated_at: string;   // ISO
}

interface GithubIssueLive {
  id: string;
  repo: string;
  title: string;
  html_url: string;
  updated_at: string;   // ISO
}

interface GithubCIRunLive {
  repo: string;
  status: 'success' | 'failure' | 'running' | 'pending';
  ran_at: string;        // ISO
  html_url: string;
}
```

**Frontend hook — `frontend/src/hooks/useGitHubState.ts`**

```typescript
export function useGitHubState(): {
  data: GitHubStatePayload | null;
  loading: boolean;
}
```

The hook subscribes via a `subscribeGitHubState` function added to `useWebSocket`'s return
value, matching the existing `subscribeSystem` / `subscribeNotifications` pattern.

**`config/config.yaml` additions**

```yaml
github:
  enabled: false          # opt-in; requires GITHUB_TOKEN in .env
  poll_interval_seconds: 45
  repos:
    - "owner/repo-a"
    - "owner/repo-b"
```

**REST endpoints:** None new. The GitHub client calls the public GitHub REST API
(`https://api.github.com`) directly. No new JARVIS HTTP routes are added.

### External dependencies
- No new pip packages. Uses `aiohttp` (already in `requirements.txt` via openclaw) for
  GitHub HTTP calls.
- No new npm packages. Frontend types and hook are pure TypeScript.

## Edge Cases & Failure Modes

- **`GITHUB_TOKEN` absent or empty at startup** → poller does not start; `DevPanel` renders
  mock data silently; no error logged at WARNING or above (DEBUG only).
- **`github.enabled: false`** → same as token absent; poller skipped entirely.
- **Token expired / revoked (401)** → `GitHubAuthError` raised in client; poller catches it,
  logs at ERROR, sets `stale=True` on cached payload, stops retrying until restart.
- **Rate limit hit (403 / 429 with `X-RateLimit-Remaining: 0`)** → `GitHubRateLimitError`;
  poller logs at WARNING, skips this tick, doubles the wait for the next tick (up to
  `poll_interval_seconds * 4`), then resumes normal cadence.
- **Partial failure (one repo's CI fetch fails, others succeed)** → failed repo omitted from
  `ci` list; remaining data broadcast normally; `stale` remains `False` (partial is not
  stale).
- **Network timeout during poll** → `aiohttp.ClientTimeout` set to 10 s; on timeout, poller
  catches exception, marks `stale=True`, broadcasts last cached payload.
- **`repos` list is empty** → CI section in payload is `[]`; PRs and issues still fetched.
- **No connected WS clients** → poller still runs on schedule to keep cache warm; broadcast
  is a no-op.
- **First client connects before first poll completes** → `last_state` is `None`; no
  `github_state` message sent for that client until first poll resolves; `DevPanel` shows
  mock data (loading state) in the meantime.
- **WS reconnect mid-session** → on reconnect, `ws_server.py` sends `last_state`
  immediately if available (same pattern as `system` metrics).
- **RPi 4 constraint** → `aiohttp` is non-blocking; poll frequency (45 s default) is low
  enough to be negligible on RPi 4. No thread-pool usage.

## Acceptance Criteria

1. With a valid `GITHUB_TOKEN` and at least one repo in `github.repos`, the backend emits a
   `github_state` WS message within 5 s of the first client connecting.
2. The `github_state` payload contains `prs`, `issues`, and `ci` arrays whose items match
   the schema defined in Interfaces above (validated by the backend unit test and the TS
   type compiler).
3. `DevPanel` (expanded) renders live PR titles, issue titles, and CI badge statuses from
   the received payload, replacing mock data.
4. `DevPanel` (compact) shows correct live PR count and issue count.
5. After `poll_interval_seconds` elapses, a second `github_state` message is broadcast and
   `DevPanel` updates without a page reload.
6. When `GITHUB_TOKEN` is absent or `github.enabled: false`, `DevPanel` falls back to mock
   data and no error is logged at WARNING or above.
7. A mocked 401 response from GitHub causes `GitHubAuthError` to be raised, the poller to
   stop, and `stale: true` in the cached payload.
8. A mocked 429 / rate-limit response causes the poller to skip one tick (no crash, no
   error broadcast to the frontend).
9. `pytest tests/integrations/github/` passes with 100% of new test cases green, all HTTP
   calls mocked via `aioresponses`.
10. `npm run test -- useGitHubState` passes; the hook correctly populates `data` from a
    mocked WS `github_state` frame and resets to `null` on disconnect.
11. TypeScript compilation (`npm run build`) produces zero new errors after the `types.ts`
    changes.

## Implementation Plan

1. `backend-dev` → create `src/integrations/github/__init__.py` exporting `GitHubClient`
   and `GitHubPoller`.
2. `backend-dev` → implement `src/integrations/github/client.py`: `GitHubClient` with
   `fetch_my_prs`, `fetch_my_issues`, `fetch_ci_status`; `GitHubAuthError`;
   `GitHubRateLimitError`; `aiohttp.ClientTimeout` of 10 s on all calls; loguru logging.
3. `backend-dev` → implement `src/integrations/github/poller.py`: `GitHubPoller` with
   `start` / `stop` / `last_state`; exponential back-off on rate-limit; stale-flag logic.
4. `backend-dev` → modify `src/api/ws_server.py`: read `github` config + `GITHUB_TOKEN`
   env var at startup; instantiate and `await poller.start()` inside the existing server
   startup coroutine; add `broadcast_github_state` helper using the existing
   `_connected_clients` set; send `last_state` immediately to newly connected clients (WS
   handshake handler).
5. `backend-dev` → add `github:` block to `config/config.yaml` with `enabled: false`,
   `poll_interval_seconds: 45`, `repos: []` as safe defaults.
6. `tester` → write `tests/integrations/github/test_client.py`: unit tests for
   `GitHubClient` covering happy path, 401 auth error, 429 rate limit, timeout, empty
   results — all HTTP mocked with `aioresponses`.
7. `tester` → write `tests/integrations/github/test_poller.py`: unit tests for
   `GitHubPoller` covering first-tick broadcast, stale-flag on failure, rate-limit back-off,
   stop cancels task cleanly.
8. `frontend-dev` → extend `frontend/src/types.ts`: add `GithubPRLive`, `GithubIssueLive`,
   `GithubCIRunLive`, `GitHubStatePayload` interfaces; add
   `| { type: 'github_state'; payload: GitHubStatePayload }` to `WsIncoming` union.
9. `frontend-dev` → extend `frontend/src/hooks/useWebSocket.ts`: add
   `subscribeGitHubState` to the module-level registry (matching `subscribeSystem`
   pattern); emit to listeners when `type === 'github_state'` is received; add
   `subscribeGitHubState` to `UseWebSocketReturn`.
10. `frontend-dev` → create `frontend/src/hooks/useGitHubState.ts`: calls
    `subscribeGitHubState`, returns `{ data, loading }`.
11. `frontend-dev` → modify `frontend/src/components/panels/DevPanel.tsx`: call
    `useGitHubState()`; when `data` is non-null replace PR and CI sections with live data;
    add `[stale]` label to GitHub section header when `data.stale === true`; preserve mock
    fallback when `data` is `null`.
12. `tester` → write `frontend/src/hooks/__tests__/useGitHubState.test.ts`: mock WS frame
    delivery, assert `data` populates correctly; assert `loading` transitions.
13. `reviewer` → review all files from steps 1–12 against this spec; emit `PASS` or
    `NEEDS_CHANGES`.

## Manual Verification

```bash
# 1. Add token to .env
echo "GITHUB_TOKEN=ghp_your_token_here" >> .env

# 2. Enable feature and add a real repo you have access to
#    Edit config/config.yaml:
#    github:
#      enabled: true
#      poll_interval_seconds: 15   # shorten for testing
#      repos: ["your-org/your-repo"]

# 3. Start backend
PYTHONPATH=src .venv/bin/python -m main

# 4. Start frontend
cd frontend && npm run dev

# 5. Open http://localhost:5173 — navigate to the DevPanel (expanded)
#    Within 5 s the GitHub section should show live PRs and CI status.
#    Check the backend log for:
#      [github_poller] poll complete: 3 prs, 1 issues, 2 ci runs

# 6. Remove the token and restart — confirm panel renders mock data,
#    no WARNING/ERROR in logs.

# 7. Run unit tests
PYTHONPATH=src .venv/bin/pytest tests/integrations/github/ -v
cd frontend && npm run test -- useGitHubState
```

## Open Questions

1. The `fetch_my_prs` query should return PRs "involving" the authenticated user — this
   covers both authored and assigned. GitHub's search API supports
   `is:pr is:open involves:@me`. Confirm this is the correct scope, or should it be
   limited to `author:@me` or `review-requested:@me` only?
2. Should the issue list include only issues where the user is the assignee (`assignee:@me`)
   or also mentioned (`involves:@me`)? The distinction matters for busy repos.
3. The `repos` config list drives CI fetches. Should PRs and issues also be scoped to only
   those repos, or should they span all repos the token can access? Spanning all repos is
   more useful but potentially slower.
4. Is a 45-second default poll interval acceptable, or should it default to 60 s to be
   more conservative on GitHub's rate-limit budget (5 000 req/hr for classic PAT)?
