# Feature: GitHub Integration — Migration to OpenClaw Cron + `github` Skill

## Status
Planned — awaiting implementation authorization

## Goal
Replace the custom aiohttp-based GitHub poller (`src/integrations/github/`) with an
OpenClaw isolated cron job that invokes the built-in `github` skill (a `gh` CLI
wrapper). The DevPanel continues to receive live `github_state` WS messages at
the same cadence and with the same payload shape as today, but without any
Python GitHub code, without a `GITHUB_TOKEN` in `.env`, and without exposure to
the Search API's 30 req/h hard cap.

This feature is the implementation of the **Tier 1.5** item in
`.tmp/features/openclaw-dedup-analysis.md` ("src/integrations/github/ komplett").

---

## Scope

### In scope
- Delete `src/integrations/github/client.py`, `src/integrations/github/poller.py`,
  `src/integrations/github/__init__.py`, and the entire `tests/integrations/github/`
  directory (36 tests).
- Register a new OpenClaw isolated cron job (`openclaw cron add`) that fires every
  60 seconds and calls `gh pr list`, `gh issue list`, and `gh run list` for each
  configured repo.
- Add a new JARVIS HTTP endpoint `POST /api/github/push` on `:8766` that receives
  the JSON state from the cron job's webhook delivery and broadcasts a `github_state`
  WS message to all connected frontend clients.
- Add a shared webhook token for cron-to-JARVIS delivery, stored in `.env`.
- Introduce `github.use_openclaw_cron: true` feature flag in `config/config.yaml`
  so the legacy Python path can be re-enabled without a code revert.
- Remove `GITHUB_TOKEN` from `.env` after the cron job is confirmed stable
  (documented in the rollback plan — not removed in this PR).
- Preserve `github.repos` in `config/config.yaml` as the authoritative repo list;
  the cron job prompt reads this list from a workspace file that is written by
  JARVIS on startup.
- Update `broadcast_github_state` in `src/api/ws_server.py` to accept a plain
  `dict` (JSON-parsed body from the webhook) rather than a `GitHubStatePayload`
  dataclass instance.
- Update the `_start_github_poller` / shutdown logic in `src/api/ws_server.py`
  to be a no-op when `github.use_openclaw_cron: true`.
- Add `JARVIS_GITHUB_WEBHOOK_TOKEN` to `.env` for JARVIS-side validation.
- Write a new pytest module `tests/api/test_github_push.py` covering the new
  endpoint.
- Add a stale-flag escalation path: if JARVIS has not received a push from the
  cron job within `github.stale_after_seconds` (default 180 s), JARVIS marks the
  last cached state as `stale: true` and rebroadcasts it.
- Update `SOUL.md` / `AGENTS.md` in the OpenClaw workspace to document the new
  cron job.

### Out of scope
- Migrating the GitLab poller (separate integration, separate risk).
- Modifying any frontend TypeScript file (`frontend/src/types.ts:376–382`,
  `frontend/src/hooks/useGitHubState.ts`, `frontend/src/hooks/useWebSocket.ts`).
- Changing the `github_state` WS message shape in `frontend/src/types.ts`.
- Adding voice-triggered on-demand GitHub queries via the `github` skill (a
  separate, additive feature).
- Deleting `GITHUB_TOKEN` from `.env` in this PR (deferred to a follow-up once
  the cron job is proven stable over 24 h).
- Adding a new OpenClaw plugin or custom skill — the built-in `github` skill is used
  as-is.
- Migrating the `GET /api/config/repos` and `POST /api/config/repos` endpoints
  (they remain; the frontend DevPanel can still update `github.repos`).

---

## User Flow

1. JARVIS backend starts. Because `github.use_openclaw_cron: true`, the legacy
   poller is not started. JARVIS writes the current `github.repos` list (from
   `config/config.yaml`) into `~/.openclaw/workspace/state/github-repos.json`.
2. The OpenClaw cron job fires every 60 seconds in an isolated session. Its
   prompt tells it to read `~/.openclaw/workspace/state/github-repos.json`,
   call `gh pr list`, `gh issue list`, and `gh run list` for each repo, assemble
   the payload into the canonical JSON schema, and POST it to
   `http://127.0.0.1:8766/api/github/push` with the shared webhook token.
3. JARVIS receives the POST, validates the token, parses and validates the JSON
   body, updates its in-memory cache, and broadcasts a `github_state` WS message
   to all connected frontend clients.
4. The DevPanel's `useGitHubState` hook receives the message exactly as before
   and re-renders with the new PR count, titles, issues, and CI badge.
5. If the cron job misses two consecutive ticks (as detected by JARVIS's
   `stale_after_seconds` watchdog), JARVIS rebroadcasts the last known state
   with `stale: true`.

---

## Architecture

### Transport option chosen: (b) OpenClaw Cron → HTTP POST to JARVIS

**Decision rationale:**

Option (a) — file polling via watchdog/inotify — would require the `watchdog` pip
package, adds an OS-level inotify dependency that does not exist on all RPi targets,
and introduces a latency floor of the poll interval (10 s minimum). It also couples
the cron output path to a filesystem path that both processes share, which is fragile
if the workspace directory changes.

Option (c) — subscribing to an OpenClaw Gateway event channel — was investigated.
The OpenClaw cron documentation (`/home/paps/Repos/openclaw/docs/automation/cron-jobs.md`)
describes three delivery modes: `announce` (to a chat channel), `webhook` (POST to a URL),
and `none` (internal only). There is no documented mechanism for a third-party process
to subscribe to cron completion events from outside the gateway. The gateway exposes
HTTP at `:18789` for inbound hook triggers (`POST /hooks/wake`, `POST /hooks/agent`)
but not an outbound event stream for cron results that a Python process could consume.

Option (b) maps directly onto the documented `webhook` delivery mode for isolated
cron jobs (`--delivery webhook --url <url>`). The cron job POSTs its output as a
structured JSON body to JARVIS's own HTTP port, which already exists on `:8766`.
This approach:

- Requires no new pip dependencies.
- Is the documented idiom for cron-to-external-service delivery in OpenClaw.
- Keeps the boundary explicit: OpenClaw pushes; JARVIS consumes.
- Works equally well on RPi (loopback POST to localhost).
- The webhook token is a simple shared secret in `.env`; no OAuth or mTLS needed
  for a loopback endpoint.

**Webhook delivery for isolated cron jobs** is configured via `--delivery webhook`
and `--url`. The cron payload is the full isolated run output (plain text). Because
the LLM produces text, the cron job's `--message` prompt instructs it to produce
exactly the JSON body; JARVIS's handler parses the response body directly.

However: OpenClaw's webhook delivery posts the **agent's text response**, not
structured JSON under a defined envelope. To keep JARVIS's handler simple, the
cron job prompt must produce a response whose first and only line is valid JSON
matching the `GitHubStatePayload` schema. The handler strips markdown fences if
present (the LLM occasionally wraps JSON in ` ```json ``` `).

Alternative to naked LLM JSON: the cron job could write a temp file and the JARVIS
handler reads it. But this re-introduces (a)'s filesystem coupling. Keeping (b) with
a strict prompt and a JSON-extraction step in the handler is simpler.

### Modules touched

- Backend:
  - `src/api/ws_server.py` — remove `_start_github_poller`, `_github_poller`,
    `_github_session` globals; update `broadcast_github_state` to accept `dict`;
    add `POST /api/github/push` handler; add stale-watchdog task.
  - `src/integrations/github/client.py` — **deleted**
  - `src/integrations/github/poller.py` — **deleted**
  - `src/integrations/github/__init__.py` — **deleted**
  - `tests/integrations/github/test_client.py` — **deleted**
  - `tests/integrations/github/test_poller.py` — **deleted**
  - `tests/integrations/github/__init__.py` — **deleted**
  - `tests/api/test_github_push.py` — **new**

- Frontend: none (no changes).

- Config:
  - `config/config.yaml` — add `github.use_openclaw_cron: true`,
    `github.stale_after_seconds: 180`, `github.webhook_path: /api/github/push`.
    Remove `github.poll_interval_seconds` (kept for legacy fallback path only,
    no-op when `use_openclaw_cron: true`).

- Env:
  - `.env` — add `JARVIS_GITHUB_WEBHOOK_TOKEN=<random-hex>`.
    `GITHUB_TOKEN` is **not removed in this PR** (preserved for legacy fallback).

- OpenClaw workspace:
  - `~/.openclaw/workspace/state/github-repos.json` — written by JARVIS on startup
    (not a tracked file, generated at runtime).
  - `~/.openclaw/workspace/SOUL.md` — add one line noting the github-state cron job.
  - `~/.openclaw/cron/jobs.json` — managed by `openclaw cron add` CLI; not edited
    directly.

### Data flow

```
JARVIS startup
  └── github.use_openclaw_cron: true
        └── write ~/.openclaw/workspace/state/github-repos.json
              (list of repos from config/config.yaml → github.repos)

OpenClaw Gateway (every 60 s)
  └── isolated cron job fires
        └── LLM reads github-repos.json via exec/read tool
        └── for each repo:
              gh pr list --repo <repo> --state open --json number,title,author,url,updatedAt
              gh issue list --repo <repo> --assignee @me --state open --json number,title,url,updatedAt
              gh run list --repo <repo> --limit 1 --json status,conclusion,url,createdAt
        └── LLM assembles GitHubStatePayload JSON
        └── delivery: webhook → POST http://127.0.0.1:8766/api/github/push
              Header: Authorization: Bearer <JARVIS_GITHUB_WEBHOOK_TOKEN>
              Body: { "prs": [...], "issues": [...], "ci": [...],
                      "fetched_at": "<ISO>", "stale": false }

JARVIS HTTP handler (ws_server.py :8766)
  └── POST /api/github/push
        └── validate Bearer token → 401 on mismatch
        └── parse JSON body → extract GitHubStatePayload dict
        └── update _github_last_state cache + reset stale watchdog timer
        └── call broadcast_github_state(dict)
              └── serialize → {"type": "github_state", "payload": {...}}
              └── _broadcast() → all connected WebSocket clients

JARVIS stale watchdog (asyncio.Task, fires every 30 s)
  └── if now - _github_last_push_ts > stale_after_seconds:
        └── rebroadcast _github_last_state with stale: true

Frontend (DevPanel / useGitHubState.ts)
  └── receives {"type": "github_state", "payload": {...}} — unchanged
```

### Interfaces

**Python — new handler signature in `src/api/ws_server.py`:**

```
async def github_push_handler(request: web.Request) -> web.Response
    # POST /api/github/push
    # Validates JARVIS_GITHUB_WEBHOOK_TOKEN, parses body JSON,
    # calls broadcast_github_state(body_dict), resets stale timer.
    # Returns 200 on success, 401 on bad token, 400 on bad JSON.

async def broadcast_github_state(payload: dict[str, Any]) -> None
    # Updated signature: accepts plain dict instead of GitHubStatePayload dataclass.
    # Serialises to {"type": "github_state", "payload": payload} and broadcasts.

async def _github_stale_watchdog(stale_after: int) -> None
    # New asyncio task. Every 30 s checks _github_last_push_ts.
    # If elapsed > stale_after and _github_last_state is not None,
    # rebroadcasts with stale: true.

async def _write_github_repos_file(repos: list[str]) -> None
    # Writes repos list to ~/.openclaw/workspace/state/github-repos.json.
    # Called from setup_server() when use_openclaw_cron: true.
```

**WebSocket message — no change:**
```
{ "type": "github_state", "payload": GitHubStatePayload }
```
`GitHubStatePayload` shape is defined at `frontend/src/types.ts:376–382`; unchanged.

**REST endpoint — new:**
```
POST http://127.0.0.1:8766/api/github/push
Headers:
  Authorization: Bearer <JARVIS_GITHUB_WEBHOOK_TOKEN>
  Content-Type: application/json
Body (GitHubStatePayload JSON):
{
  "prs": [
    { "id": "string", "repo": "string", "title": "string",
      "author": "string", "html_url": "string", "updated_at": "ISO" }
  ],
  "issues": [
    { "id": "string", "repo": "string", "title": "string",
      "html_url": "string", "updated_at": "ISO" }
  ],
  "ci": [
    { "repo": "string", "status": "success|failure|running|pending",
      "ran_at": "ISO", "html_url": "string" }
  ],
  "fetched_at": "ISO",
  "stale": false
}
Response 200: { "ok": true }
Response 400: { "ok": false, "error": "invalid JSON | missing field" }
Response 401: { "ok": false, "error": "unauthorized" }
```

### External dependencies

- No new pip packages.
- `gh` CLI: already installed and authenticated (`gh auth login`, scopes:
  repo / read:org / workflow). Rate limit: 5000 req/h Core API.
- OpenClaw built-in `github` skill: already available in the bundled skill set.
  No install step needed.
- OpenClaw cron: already enabled in the running gateway.

---

## OpenClaw Configuration

### Cron job registration (one-time CLI command)

```bash
openclaw cron add \
  --name "jarvis-github-state" \
  --every "60s" \
  --session isolated \
  --light-context \
  --message "$(cat <<'PROMPT'
Read the file ~/.openclaw/workspace/state/github-repos.json to get the repo list.

For each repo in the list, run these three gh commands and collect the output:
  gh pr list --repo <REPO> --state open --json id,title,author,headRefName,url,updatedAt --limit 20
  gh issue list --repo <REPO> --assignee @me --state open --json id,title,url,updatedAt --limit 20
  gh run list --repo <REPO> --limit 1 --json status,conclusion,url,createdAt

Assemble the results into a single JSON object with this exact schema:
{
  "prs": [ { "id": "<string>", "repo": "<owner/repo>", "title": "<string>", "author": "<login>", "html_url": "<url>", "updated_at": "<ISO>" } ],
  "issues": [ { "id": "<string>", "repo": "<owner/repo>", "title": "<string>", "html_url": "<url>", "updated_at": "<ISO>" } ],
  "ci": [ { "repo": "<owner/repo>", "status": "<success|failure|running|pending>", "ran_at": "<ISO>", "html_url": "<url>" } ],
  "fetched_at": "<ISO 8601 UTC now>",
  "stale": false
}

Map gh run status/conclusion to JARVIS status values:
  in_progress → "running", queued → "pending", success conclusion → "success",
  failure/timed_out/cancelled conclusion → "failure", anything else → "pending".

Use the id field from gh json output as a string. Set repo to "owner/repo" format.
Output ONLY the JSON object, no markdown fences, no explanation.
PROMPT
)" \
  --delivery webhook \
  --webhook-url "http://127.0.0.1:8766/api/github/push" \
  --webhook-header "Authorization: Bearer ${JARVIS_GITHUB_WEBHOOK_TOKEN}"
```

**Note on `--delivery webhook` for isolated jobs:** The OpenClaw cron docs
(`/home/paps/Repos/openclaw/docs/automation/cron-jobs.md`, delivery table) confirm
`webhook` mode POSTs the finished event payload to the given URL. The agent is
prompted to return its result as plain text; that text is the POST body.
The `--webhook-header` flag passes the auth header.

### `~/.openclaw/openclaw.json` additions

No structural changes are required for this feature. The cron job is registered
via CLI and stored in `~/.openclaw/cron/jobs.json`. The gateway's existing
`cron.enabled: true` default is sufficient.

### `config/config.yaml` changes

```yaml
github:
  enabled: true
  # When true, the Python aiohttp poller is not started; state arrives
  # from the OpenClaw cron job via POST /api/github/push.
  use_openclaw_cron: true
  # poll_interval_seconds is ignored when use_openclaw_cron: true.
  # Retained here so the legacy path still works when the flag is false.
  poll_interval_seconds: 60
  repos:
    - "JoeyAsh/javis"
  # Seconds of silence from the cron job before the last known state is
  # rebroadcast with stale: true.
  stale_after_seconds: 180
  # Path for the inbound cron webhook.
  webhook_path: "/api/github/push"
```

### `.env` additions

```
JARVIS_GITHUB_WEBHOOK_TOKEN=<64-char hex — generate with: openssl rand -hex 32>
```

---

## State Schema (canonical)

The `GitHubStatePayload` shape that the cron job must produce and JARVIS's handler
must validate against is defined at `frontend/src/types.ts:376–382`:

```typescript
interface GitHubStatePayload {
  prs: GithubPRLive[];      // types.ts:348–356
  issues: GithubIssueLive[]; // types.ts:358–364
  ci: GithubCIRunLive[];    // types.ts:366–373
  fetched_at: string;        // ISO 8601
  stale: boolean;
}
```

Sub-object shapes (`GithubPRLive`, `GithubIssueLive`, `GithubCIRunLive`) are
defined at `frontend/src/types.ts:348–373`. These are identical to what the old
`broadcast_github_state` function (at `src/api/ws_server.py:548–582`) serialised
from the Python dataclasses. No frontend change is needed.

JARVIS's handler performs minimal validation: it checks that `prs`, `issues`, `ci`,
`fetched_at`, and `stale` keys are present. It does not deep-validate sub-object
fields — missing fields in sub-objects pass through to the frontend as-is (the
frontend already handles missing optional fields gracefully).

---

## Edge Cases and Failure Modes

- **Cron job produces invalid JSON** → `github_push_handler` returns 400; the
  last known state is preserved; the stale watchdog escalates to `stale: true`
  after `stale_after_seconds`. JARVIS logs at WARNING with the raw body snippet.

- **Cron job wraps JSON in markdown fences** → the handler strips leading/trailing
  ` ```json ``` ` or ` ``` ``` ` blocks before parsing. If stripping fails, the
  raw parse attempt is tried first.

- **Cron job misses a tick** → OpenClaw cron retries automatically (up to 3 times
  with backoff, per `cron.retry` config). JARVIS stale watchdog fires at
  `stale_after_seconds` (default 180 s = 3 missed ticks at 60 s cadence).

- **OpenClaw gateway is down** → cron does not fire. JARVIS stale watchdog detects
  the gap and marks state as `stale: true`.

- **`gh` auth token expires** → `gh` CLI exits non-zero. The LLM sees the error
  output and will attempt to set `stale: true` in its JSON response (instruct via
  prompt). JARVIS handler checks: if payload has `stale: true` or body does not
  parse, it marks the cached state stale. Resolution requires `gh auth login` on
  the host.

- **`gh` rate limit hit** → 5000 req/h Core API. At 60 s cadence and 3 repos,
  each tick uses ~9 `gh` calls (3 commands × 3 repos). That is 540 calls/h — well
  within 5000. No rate-limit handling is needed beyond logging.

- **JARVIS HTTP port not listening yet** → if the cron job fires during JARVIS
  startup before `:8766` is ready, OpenClaw retries the webhook POST (the cron
  retry policy applies). JARVIS startup writes `github-repos.json` before binding
  the port; if the cron fires in the sub-second window, the retry catches it.

- **No frontend clients connected** → `broadcast_github_state` calls `_broadcast()`
  which iterates an empty set; safe no-op. The cache is still updated.

- **`github.repos` is empty** → `_write_github_repos_file` writes an empty list.
  The cron job prompt reads the empty list, runs no `gh` commands, and emits an
  empty payload (`prs: [], issues: [], ci: []`). This is a valid state, not an
  error.

- **JARVIS restarts while cron job is mid-flight** → the cron job's webhook POST
  will fail with a connection-refused error. OpenClaw will retry. On JARVIS restart,
  the in-memory cache is empty. A new client connecting before the first push
  receives no `github_state` message; the DevPanel shows its empty/placeholder
  state. This is acceptable — same behaviour as the old poller on cold start.

- **Mismatched `JARVIS_GITHUB_WEBHOOK_TOKEN`** → handler returns 401. The cron
  job delivery is marked failed by OpenClaw. After 3 retries, the job is marked
  `error`. OpenClaw logs the failure. Resolution requires token sync between `.env`
  and the cron job's registered webhook header.

- **`github.use_openclaw_cron: false` with `GITHUB_TOKEN` absent** → legacy path
  is selected but the token is missing. Existing behaviour: the poller is not
  started and a warning is logged. No regression.

- **RPi target** → `gh` CLI is installed and functional on RPi (verified in
  constraints). Loopback HTTP is available. The watchdog task adds negligible
  CPU overhead.

---

## Acceptance Criteria

1. When JARVIS starts with `github.use_openclaw_cron: true`, no `aiohttp.ClientSession`
   for GitHub is created, no `GitHubPoller` task is started, and `GITHUB_TOKEN` is
   not read from the environment.
2. `~/.openclaw/workspace/state/github-repos.json` is written on startup and
   contains exactly the repos listed in `config/config.yaml → github.repos`.
3. The OpenClaw cron job registered as `jarvis-github-state` fires every 60 s
   (±10 s jitter) and is visible in `openclaw cron list`.
4. Within 90 s of the cron job firing, a `github_state` WS message is received by
   a connected frontend client whose `payload.prs`, `payload.issues`, and
   `payload.ci` reflect the current state of `JoeyAsh/javis` on GitHub.
5. `payload.stale` is `false` on a successful cron push and `true` after 180 s
   of no push.
6. `POST /api/github/push` with a correct token and valid body returns `{"ok": true}`
   and status 200.
7. `POST /api/github/push` with an incorrect or absent `Authorization` header
   returns status 401.
8. `POST /api/github/push` with a body that is not valid JSON (or is missing a
   required top-level key) returns status 400.
9. The DevPanel (`frontend/src/components/OrbDevMenu.tsx` or equivalent consumer)
   renders updated PR count and CI badge within 5 s of a valid cron push, with no
   frontend code changes.
10. `frontend/src/types.ts` is unmodified after this feature is implemented.
11. `src/integrations/github/client.py`, `src/integrations/github/poller.py`, and
    `src/integrations/github/__init__.py` do not exist in the repository.
12. `tests/integrations/github/` does not exist in the repository.
13. When `github.use_openclaw_cron: false` is set in `config/config.yaml`, the
    legacy Python poller starts as before (regression guard).
14. `pytest tests/api/test_github_push.py` passes with 100 % coverage of the new
    handler's branches (happy path, bad token, bad JSON, missing keys).
15. `GITHUB_TOKEN` remains in `.env` (not deleted) and the backend logs at DEBUG
    that it is not used because `use_openclaw_cron` is active.

---

## Implementation Plan

1. `backend-dev` → add `github.use_openclaw_cron`, `github.stale_after_seconds`,
   and `github.webhook_path` keys to `config/config.yaml`; add
   `JARVIS_GITHUB_WEBHOOK_TOKEN` placeholder to `.env`.

2. `backend-dev` → in `src/api/ws_server.py`: update `broadcast_github_state` to
   accept `dict[str, Any]` instead of a `GitHubStatePayload` dataclass; update the
   call site at line 2861 (new-client replay) to use the dict cache.

3. `backend-dev` → in `src/api/ws_server.py`: add `_github_last_state: dict | None`
   and `_github_last_push_ts: float` module-level variables; add
   `github_push_handler` (validates token, strips markdown fences, parses JSON,
   updates cache, calls `broadcast_github_state`, resets timestamp); add handler to
   the `http_app` router as `POST /api/github/push`.

4. `backend-dev` → in `src/api/ws_server.py`: add `_github_stale_watchdog`
   asyncio task (30 s poll, broadcasts cached state with `stale: true` when
   `time.monotonic() - _github_last_push_ts > stale_after_seconds`); start it in
   `setup_server()` when `use_openclaw_cron: true`.

5. `backend-dev` → in `src/api/ws_server.py`: add `_write_github_repos_file` that
   writes `github.repos` to `~/.openclaw/workspace/state/github-repos.json`; call
   it from `setup_server()` when `use_openclaw_cron: true` before binding the HTTP
   port.

6. `backend-dev` → in `src/api/ws_server.py`: gate the `_start_github_poller` call
   block behind `not github_cfg.get("use_openclaw_cron", False)`; gate the shutdown
   block for `_github_poller` / `_github_session` the same way; log at DEBUG when
   the poller is skipped.

7. `backend-dev` → delete `src/integrations/github/client.py`,
   `src/integrations/github/poller.py`, `src/integrations/github/__init__.py`.

8. `backend-dev` → delete `tests/integrations/github/test_client.py`,
   `tests/integrations/github/test_poller.py`,
   `tests/integrations/github/__init__.py` (the directory itself).

9. `tester` → create `tests/api/test_github_push.py`: unit tests for
   `github_push_handler` covering: valid push updates cache and triggers broadcast;
   invalid token returns 401; body not JSON returns 400; body missing required key
   returns 400; markdown-fenced JSON is stripped and accepted; stale watchdog
   emits stale rebroadcast after threshold.

10. `backend-dev` → update `~/.openclaw/workspace/SOUL.md` to add one bullet noting
    that the `jarvis-github-state` cron job runs every 60 s and pushes GitHub state
    to JARVIS via `POST http://127.0.0.1:8766/api/github/push`.

11. `backend-dev` → register the cron job via `openclaw cron add` (see CLI command
    in the OpenClaw Configuration section above); document the job ID in a comment
    in `config/config.yaml`.

12. `reviewer` → review all changed / new files against this spec; verify that no
    frontend file has been touched; verify that `frontend/src/types.ts` is byte-for-byte
    unchanged; verify that the `GitHubStatePayload` WS message shape is identical to
    the pre-migration shape.

---

## Rollback Plan

**Goal:** restore the old behaviour in under 5 minutes without a code revert.

1. Set `github.use_openclaw_cron: false` in `config/config.yaml`.
2. Ensure `GITHUB_TOKEN` is still present in `.env` (it is — not deleted in this PR).
3. Restart JARVIS (`PYTHONPATH=src .venv/bin/python -m main`).

The legacy code (`src/integrations/github/`) was **deleted** in step 7 of the
implementation plan. A full code rollback (`git revert <commit>`) restores it.

**Two-PR strategy (recommended):** Land this feature in one PR. Defer the deletion
of `GITHUB_TOKEN` from `.env` to a separate follow-up PR, opened only after the
cron job has been observed running reliably for 24 hours. This gives a clean
rollback path (just flip the config flag) without any code revert for the first 24 h.

---

## Manual Verification

After implementation, run these steps locally to sanity-check the feature:

```bash
# 1. Confirm cron job is registered
openclaw cron list

# 2. Start JARVIS and tail logs — confirm poller is NOT started
PYTHONPATH=src .venv/bin/python -m main 2>&1 | grep -i github

# 3. Confirm github-repos.json was written
cat ~/.openclaw/workspace/state/github-repos.json

# 4. Simulate a cron push manually
curl -s -X POST http://127.0.0.1:8766/api/github/push \
  -H "Authorization: Bearer $(grep JARVIS_GITHUB_WEBHOOK_TOKEN .env | cut -d= -f2)" \
  -H "Content-Type: application/json" \
  -d '{
    "prs": [{"id": "1", "repo": "JoeyAsh/javis", "title": "Test PR",
             "author": "JoeyAsh", "html_url": "https://github.com/JoeyAsh/javis/pull/1",
             "updated_at": "2026-04-18T12:00:00Z"}],
    "issues": [],
    "ci": [{"repo": "JoeyAsh/javis", "status": "success",
            "ran_at": "2026-04-18T12:00:00Z",
            "html_url": "https://github.com/JoeyAsh/javis/actions/runs/1"}],
    "fetched_at": "2026-04-18T12:00:00Z",
    "stale": false
  }'
# Expected: {"ok": true}

# 5. Open the HUD in the browser and confirm the DevPanel updates

# 6. Test bad token
curl -s -o /dev/null -w "%{http_code}" -X POST http://127.0.0.1:8766/api/github/push \
  -H "Authorization: Bearer wrong-token" -H "Content-Type: application/json" -d '{}'
# Expected: 401

# 7. Force-run the cron job and observe the push in JARVIS logs
openclaw cron run <jobId from step 1>

# 8. Run pytest for the new tests
PYTHONPATH=src pytest tests/api/test_github_push.py -v

# 9. Confirm legacy path still works
#    Set github.use_openclaw_cron: false in config.yaml + restart + check logs
```

---

## Open Questions

1. **Cron webhook header flag name**: The OpenClaw cron docs show `--delivery webhook`
   and `--url` for cron webhook delivery, but the exact flag for custom HTTP headers
   (`--webhook-header`) needs to be verified against the live `openclaw cron add --help`
   output before registering the job. If the flag does not exist, the fallback is to
   omit the auth header and instead validate the source IP address (loopback only)
   in `github_push_handler`.

2. **Markdown-fence stripping reliability**: The LLM (Claude) occasionally wraps
   JSON in ` ```json ``` `. The handler will strip known fence patterns. However,
   if the LLM produces multi-turn output with explanatory text before the JSON,
   the extraction will fail. Should the cron prompt be hardened with an additional
   system-level instruction, or should the handler attempt to extract the last
   valid JSON object from the body? Decision deferred to the backend-dev implementing
   step 3.

3. **`--every 60s` precision**: The OpenClaw cron docs note that top-of-hour
   expressions are auto-staggered. For `--every "60s"` (interval-based, not
   cron-expression-based), staggering should not apply. Verify with a 5-minute
   observation window after registration.

4. **`GITHUB_TOKEN` deletion timeline**: This spec defers deletion to a follow-up
   PR. Who should trigger that PR — the user manually, or should a calendar reminder
   be set via OpenClaw cron to prompt the user after 24 h of stable operation?
