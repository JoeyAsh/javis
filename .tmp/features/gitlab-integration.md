# Feature: GitLab Work Items Integration

## Status
Planned — awaiting implementation authorization

## Goal
Surface live GitLab data — open Issues assigned to the user, open Merge Requests
(authored or review-requested), and Pipeline status for configured projects — in a
dedicated HUD panel. Eliminates the need to switch to a browser tab just to triage
work items, keeping all dev-context in the JARVIS HUD.

## Scope
### In scope
- Backend async client at `src/integrations/gitlab/client.py` using raw `aiohttp`
  (see Architecture note on library choice).
- Polling loop (default 60 s) that pushes `gitlab_state` WS events to all clients.
- `config.yaml` `gitlab:` block: `enabled`, `url`, `poll_interval`, `projects`.
- `GITLAB_TOKEN` and `GITLAB_URL` read from `.env` (already populated).
- New HUD panel `GitLabPanel.tsx` with compact and expanded modes.
- Panel registered in `PanelId`, `DEFAULT_ASSIGNMENTS` (slot `R2`), `panels/index.ts`,
  and `HudWindows.tsx` switch.
- `gitlab_state` added to `WsIncoming` in `types.ts`.
- Unit tests for the backend client (mocked HTTP) and component tests for the panel.

### Out of scope
- Voice intents / orchestrator routing — MVP is panel-only.
- Webhooks — polling only.
- Creating / updating issues or MRs from JARVIS.
- GitLab CI artifact download or log streaming.
- Multi-account (single token only).
- Pagination beyond first page of results (50 items per resource type is enough for
  a HUD summary; add in a follow-up if needed).

## User Flow
1. User opens JARVIS. On startup the backend reads `gitlab.enabled` from config; if
   true it starts the poll loop.
2. Within `poll_interval` seconds (default 60 s) the first `gitlab_state` WS event
   arrives at the frontend.
3. `GitLabPanel` (slot `R2` by default) renders MR count, Issue count, and a
   per-project pipeline badge row.
4. On hover / maximize the panel shows the full list: MR titles + source branch,
   Issue titles + labels, Pipeline project + status + link.
5. If the token is invalid or the network is unreachable the panel shows an error
   badge; the backend logs at WARNING and retries on the next tick.

## Architecture

### Modules touched
- Backend: `src/integrations/gitlab/__init__.py`, `src/integrations/gitlab/client.py`,
  `src/integrations/gitlab/poller.py`, `src/api/ws_server.py`
- Frontend: `frontend/src/components/panels/GitLabPanel.tsx`,
  `frontend/src/components/panels/index.ts`,
  `frontend/src/components/hud/HudWindows.tsx`,
  `frontend/src/components/hud/SlotGrid.ts`,
  `frontend/src/types.ts`
- Config: `config/config.yaml` — new `gitlab:` section
- Env: `GITLAB_TOKEN` (already present), `GITLAB_URL` (already present, optional)

### Library choice — raw `aiohttp` over `python-gitlab`
`python-gitlab` is synchronous-first; its async support is a thin wrapper that still
blocks the event loop for some operations. The JARVIS backend is fully `asyncio`-based
(aiohttp WS server). Using raw `aiohttp` sessions keeps the integration consistent
with the rest of the codebase (`integrations/openclaw/ws_client.py` does the same)
and avoids a dependency whose async story is underdocumented. All GitLab REST v4
endpoints used here are stable and simple enough that a thin hand-rolled client is
the lower-risk choice.

### Data flow

```
config.yaml + .env
       |
       v
GitLabPoller (background asyncio.Task, started in ws_server.start_ws_server)
       |
       | every poll_interval seconds
       v
GitLabClient.fetch_state()
  ├── GET /api/v4/merge_requests?scope=assigned_to_me&state=opened
  ├── GET /api/v4/issues?scope=assigned_to_me&state=opened
  └── for each project in config:
        GET /api/v4/projects/<encoded>/pipelines?per_page=1&order_by=id&sort=desc
       |
       v
GitLabState dataclass
       |
       v
broadcast_gitlab_state(state)   [ws_server.py]
       |
       v
WS frame: { type: "gitlab_state", payload: GitLabStatePayload }
       |
       v
useWebSocket hook (frontend) → GitLabPanel renders
```

### Interfaces

**Python — `src/integrations/gitlab/client.py`**

```
@dataclass
class GitLabMR:
    id: int
    iid: int
    title: str
    source_branch: str
    web_url: str
    author: str
    created_at: str          # ISO 8601
    draft: bool

@dataclass
class GitLabIssue:
    id: int
    iid: int
    title: str
    labels: list[str]
    web_url: str
    author: str
    created_at: str

@dataclass
class GitLabPipeline:
    project: str             # "group/project" slug
    status: str              # "success" | "failed" | "running" | "pending" | "canceled"
    web_url: str
    created_at: str

@dataclass
class GitLabState:
    mrs: list[GitLabMR]
    issues: list[GitLabIssue]
    pipelines: list[GitLabPipeline]
    error: str | None        # set if any fetch failed; partial data still returned

class GitLabClient:
    def __init__(self, token: str, url: str, projects: list[str]) -> None: ...
    async def fetch_state(self) -> GitLabState: ...
    async def close(self) -> None: ...
```

**Python — `src/integrations/gitlab/poller.py`**

```
class GitLabPoller:
    def __init__(self, client: GitLabClient, interval_seconds: int) -> None: ...
    async def run(self, on_state: Callable[[GitLabState], Awaitable[None]]) -> None: ...
    async def stop(self) -> None: ...
```

**WebSocket message — new `WsIncoming` variant**

```typescript
// type.ts addition
export interface GitLabMRPayload {
  id: number;
  iid: number;
  title: string;
  source_branch: string;
  web_url: string;
  author: string;
  created_at: string;
  draft: boolean;
}

export interface GitLabIssuePayload {
  id: number;
  iid: number;
  title: string;
  labels: string[];
  web_url: string;
  author: string;
  created_at: string;
}

export interface GitLabPipelinePayload {
  project: string;
  status: 'success' | 'failed' | 'running' | 'pending' | 'canceled' | 'skipped';
  web_url: string;
  created_at: string;
}

export interface GitLabStatePayload {
  mrs: GitLabMRPayload[];
  issues: GitLabIssuePayload[];
  pipelines: GitLabPipelinePayload[];
  error: string | null;
}

// added to WsIncoming union:
| { type: 'gitlab_state'; payload: GitLabStatePayload }
```

**REST endpoints used (GitLab API v4, no new JARVIS REST endpoints)**

| Method | GitLab path | Notes |
|--------|-------------|-------|
| GET | `/api/v4/merge_requests` | `?scope=assigned_to_me&state=opened&per_page=50` |
| GET | `/api/v4/issues` | `?scope=assigned_to_me&state=opened&per_page=50` |
| GET | `/api/v4/projects/<url-encoded-path>/pipelines` | `?per_page=1&order_by=id&sort=desc` — one per project |

### External dependencies
- No new pip packages — `aiohttp` already in `requirements.txt`.
- No new npm packages.
- GitLab personal access token with `api` + `read_repository` scopes (already in `.env`).

## Config additions (`config/config.yaml`)

```yaml
gitlab:
  enabled: true
  url: "https://gitlab.com"          # override with GITLAB_URL env var
  poll_interval: 60                  # seconds
  projects:                          # list of "group/project" slugs to watch pipelines for
    - "my-group/my-project"
```

The `url` key is overridden at runtime by `GITLAB_URL` if set. `GITLAB_TOKEN` is
always read from `.env` and never put in `config.yaml`.

## Edge Cases & Failure Modes

- **Invalid token (401)** — `fetch_state` catches `aiohttp.ClientResponseError(401)`,
  returns `GitLabState(mrs=[], issues=[], pipelines=[], error="Unauthorized — check GITLAB_TOKEN")`.
  Frontend shows an error badge; no crash, no retry storm (next poll happens at next
  normal tick).
- **Self-hosted URL misconfigured (connection refused / DNS failure)** — caught as
  `aiohttp.ClientConnectorError`; logged WARNING; panel shows error badge.
- **Project not found (404 on pipeline endpoint)** — logged WARNING for that specific
  project slug; other projects continue to succeed; partial data surfaced.
- **GitLab rate limit (429)** — `fetch_state` reads `Retry-After` header; poller
  backs off by that duration (capped at 300 s) before the next poll.
- **Partial fetch** — MRs and Issues requests can succeed while a pipeline request
  fails. `GitLabState.error` is set to the first error message; already-fetched data
  is still broadcast so the panel is not entirely blank.
- **Stale data on reconnect** — `ws_server.py` pushes the last known `GitLabState`
  snapshot to newly connecting clients (same pattern as `broadcast_system_metrics`).
  If no snapshot exists yet the panel shows a loading indicator.
- **`gitlab.enabled: false`** — poller is never started; no WS events are emitted;
  panel renders with `--text-muted` placeholder "GitLab disabled".
- **Empty `projects` list** — pipelines section is empty; MR + Issue tiles still work.
- **Very large MR/Issue list (>50)** — capped at `per_page=50` by the API query;
  expanded panel shows count badge "50+" if the list is at the limit.
- **Raspberry Pi network latency** — `aiohttp` timeout set to 10 s per request;
  total `fetch_state` timeout capped at 30 s via `asyncio.wait_for`. Poll interval
  means a single slow tick does not cascade.

## Acceptance Criteria

1. When `gitlab.enabled: true` and `GITLAB_TOKEN` is valid, a `gitlab_state` WS
   event arrives within `poll_interval + 5` seconds of backend startup.
2. `GitLabStatePayload.mrs` contains only MRs with `state=opened` assigned to the
   authenticated user (verified by mocking the GitLab API in tests).
3. `GitLabStatePayload.issues` contains only open Issues assigned to the authenticated
   user (same mock verification).
4. For each project in `gitlab.projects`, exactly one pipeline entry appears in
   `GitLabStatePayload.pipelines`, reflecting the most recent pipeline's status.
5. When `GITLAB_TOKEN` is invalid (401 mock), `GitLabStatePayload.error` is non-null
   and the panel renders an error badge instead of counts.
6. When `gitlab.enabled: false`, no `gitlab_state` event is ever emitted and the
   poller task is never created.
7. `GitLabPanel` compact mode renders three items: MR count, Issue count, and a
   pipeline status dot for the first configured project (or "—" if none).
8. `GitLabPanel` expanded mode renders full list rows for MRs, Issues, and Pipelines,
   each with title and relative-time string.
9. A newly connecting WebSocket client receives the last cached `gitlab_state` snapshot
   immediately (no waiting for the next poll tick), verified by a test that connects
   after the first poll fires.
10. The backend handles a 429 response from GitLab by waiting the `Retry-After` duration
    before the next poll, verified by a unit test that asserts the poller sleeps longer
    than `poll_interval`.
11. Panel integrates with the floating-window framework: it appears in slot `R2` by
    default, supports maximize/dock toggle, and accepts drag to other slots.

## Implementation Plan

1. `backend-dev` — create `src/integrations/gitlab/__init__.py` (package init, exports
   `GitLabClient`, `GitLabPoller`).
2. `backend-dev` — create `src/integrations/gitlab/client.py` with `GitLabClient`,
   `GitLabMR`, `GitLabIssue`, `GitLabPipeline`, `GitLabState` dataclasses and
   `fetch_state()` method; `aiohttp` session; 10 s per-request timeout; 429 backoff
   support.
3. `backend-dev` — create `src/integrations/gitlab/poller.py` with `GitLabPoller.run()`
   background loop; reads `poll_interval` from config; stores last `GitLabState`
   snapshot for new-client push.
4. `backend-dev` — update `src/api/ws_server.py`: add `broadcast_gitlab_state()`;
   start `GitLabPoller` task in `start_ws_server()` when `gitlab.enabled`; push
   cached snapshot to new connections in the per-connection handler.
5. `backend-dev` — update `config/config.yaml` with the `gitlab:` section as specified
   above.
6. `frontend-dev` — update `frontend/src/types.ts`: add `GitLabMRPayload`,
   `GitLabIssuePayload`, `GitLabPipelinePayload`, `GitLabStatePayload` interfaces;
   add `'gitlab'` to `PanelId`; add `gitlab_state` variant to `WsIncoming`.
7. `frontend-dev` — update `frontend/src/hooks/useWebSocket.ts` to handle
   `gitlab_state` messages and expose `gitLabState: GitLabStatePayload | null` from
   the hook.
8. `frontend-dev` — create `frontend/src/components/panels/GitLabPanel.tsx` with
   compact and expanded modes; follow HUD design system (JetBrains Mono, CSS vars,
   `window-compact-row`, `list-item`, accent-border hover); pipeline status dot uses
   colour convention: green=success, red=failed, amber=running/pending, grey=other.
9. `frontend-dev` — update `frontend/src/components/panels/index.ts` to export
   `GitLabPanel`.
10. `frontend-dev` — update `frontend/src/components/hud/SlotGrid.ts`:
    add `'gitlab'` to `DEFAULT_ASSIGNMENTS` at slot `R2` (displacing the current
    occupant — see Open Questions).
11. `frontend-dev` — update `frontend/src/components/hud/HudWindows.tsx`: add
    `GitLabPanel` to the panel-switch/render block; pass `gitLabState` from
    `useWebSocket`.
12. `tester` — unit tests in `tests/integrations/gitlab/test_client.py`: mock
    `aiohttp.ClientSession`; test 200 happy path, 401 error propagation, 404 project
    partial failure, 429 backoff header parsing.
13. `tester` — unit tests in `tests/integrations/gitlab/test_poller.py`: mock
    `GitLabClient.fetch_state`; verify callback fires on schedule; verify 429 extends
    sleep; verify `stop()` cancels cleanly.
14. `tester` — integration smoke test in `tests/api/test_gitlab_broadcast.py`: mock
    poller callback; assert `broadcast_gitlab_state` emits correct WS frame.
15. `tester` — component tests in `frontend/src/components/panels/__tests__/GitLabPanel.test.tsx`:
    render compact with mock data, expanded with mock data, error state, empty state.
16. `reviewer` — review all new files against this spec; issue `PASS` or `NEEDS_CHANGES`.

## Manual Verification

```bash
# 1. Start backend with real token
PYTHONPATH=src .venv/bin/python -m main

# 2. Watch for the first poll event (within poll_interval seconds)
# In a second terminal, connect a WS client:
python3 -c "
import asyncio, json, aiohttp
async def main():
    async with aiohttp.ClientSession() as s:
        async with s.ws_connect('ws://localhost:8765/ws') as ws:
            async for msg in ws:
                data = json.loads(msg.data)
                if data.get('type') == 'gitlab_state':
                    print(json.dumps(data['payload'], indent=2))
                    break
asyncio.run(main())
"

# 3. Open the frontend (http://localhost:5173) — verify GitLabPanel appears in R2 slot
# 4. Maximize the panel — verify full MR and Issue rows render
# 5. Set GITLAB_TOKEN=invalid in .env and restart — verify error badge in panel
```

## Open Questions

1. **Slot `R2` conflict** — `R2` is currently assigned to `lights` in
   `DEFAULT_ASSIGNMENTS`. Either move `lights` to a bottom-strip slot (freeing `R2`)
   or assign `gitlab` to `B2` and displace `dev`. Confirm with user before step 10.
2. **Review-requested MRs** — GitLab's `scope=assigned_to_me` covers MRs the user
   authored. Review-requested MRs require a separate query
   (`scope=all&reviewer_id=<user_id>`), which needs a prior `GET /api/v4/user` call to
   resolve the token-owner's numeric ID. Should the MVP include review-requested MRs,
   or is "assigned to me" sufficient?
3. **Project slugs vs numeric IDs** — the spec uses URL-encoded `group/project` path
   strings. If a project has been renamed or migrated, the path changes. Should the
   config also accept numeric project IDs as an alternative?
