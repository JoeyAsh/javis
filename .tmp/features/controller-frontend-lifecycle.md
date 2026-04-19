# Feature: Controller — Frontend Lifecycle Management

## Status
Planned — awaiting implementation authorization

## Goal
The JARVIS web UI (React/Vite on :5173) is currently launched manually via `npm run dev` and has no start/stop/restart control in the JARVIS Controller Tauri app. This feature brings the frontend under systemd management, adds a second sub-row inside the existing JARVIS card for frontend controls (matching the backend row's Start/Stop/Restart pattern), adds a `restart_jarvis` command for the backend row (currently missing), and gates the "Open JARVIS UI" link button on the frontend HTTP probe so the user cannot open a dead URL.

## Scope

### In scope
- New systemd user unit `ops/jarvis-frontend.service` running `npm run dev` (Vite dev server, port 5173).
- Four new Tauri commands: `start_frontend`, `stop_frontend`, `restart_frontend`, `frontend_status`.
- One new Tauri command: `restart_jarvis` (backend row was missing restart).
- Restructured JARVIS card in `controller/index.html`: two `.sub-service` rows (Backend, Frontend), each with status dot, state text, HTTP indicator, and Start/Stop/Restart buttons.
- Removal of the standalone "Open JARVIS UI →" link button from the bottom `links-row`; its function is absorbed into the frontend sub-row's HTTP-gated open button.
- Updated `controller/src/main.ts`: new DOM refs, `applyFrontendStatus`, `applyBackendStatus` (renamed from `applyJarvisStatus`), three-way parallel polling.
- Minimal CSS additions to `controller/src/style.css` for `.sub-service` rows and `.sub-service-label` dividers — no restyling of existing rules.
- One installation note in `ops/README.md` (or inline comment in the service unit) explaining the one-time `daemon-reload` + optional `enable` step.
- Vitest tests for the new wiring in `main.ts` (DOM mutations, button enable/disable logic).
- Rust unit tests for `frontend_status` and `restart_jarvis` command stubs where testable without a live systemd session.

### Out of scope
- Any changes to the JARVIS Python backend or its runtime.
- Any changes to OpenClaw lifecycle or its card.
- Auto-start-on-login configuration — the user runs `systemctl --user enable jarvis-frontend.service` manually if desired.
- A production build+preview mode (`npm run build && npm run preview`) — deferred; documented in Open Questions so the user can redirect.
- Redesigning the controller window layout or overall visual style beyond what the new sub-rows require.
- Supporting non-systemd platforms (macOS, Windows) — the controller already targets Linux/RPi only.

## User Flow

1. User opens JARVIS Controller (Tauri app).
2. The JARVIS card now shows two labelled sub-rows: **BACKEND** and **FRONTEND**.
3. Each sub-row displays a status dot (active/activating/inactive/failed), state text, and an HTTP reachability indicator.
4. Backend sub-row has Start, Stop, Restart buttons; Frontend sub-row has the same three.
5. User clicks **START** on the Frontend sub-row. The button disables immediately, a toast appears ("frontend · starting…"), and polling resumes after 300 ms.
6. Within a few seconds the Vite dev server comes up; the status dot turns active, HTTP indicator shows "reachable", and the "Open JARVIS UI →" button embedded in the frontend sub-row becomes clickable.
7. User clicks "Open JARVIS UI →"; the browser opens `http://localhost:5173`.
8. User clicks **RESTART** on the Backend sub-row; toast confirms "backend · restarted · HH:MM:SS".
9. On stop, the respective dot dims and buttons re-enable appropriately.

## Architecture

### Modules touched
- Backend (Rust): `controller/src-tauri/src/lib.rs`
- Frontend (controller UI): `controller/index.html`, `controller/src/main.ts`, `controller/src/style.css`
- Ops: `ops/jarvis-frontend.service` (new file)
- Config: none
- Env: none

### Data flow

```
Controller UI (Tauri webview)
  │
  │  every 2 s — Promise.allSettled([
  │    invoke("jarvis_status"),        ← jarvis-backend.service is-active + HTTP :8766
  │    invoke("frontend_status"),      ← jarvis-frontend.service is-active + HTTP :5173
  │    invoke("openclaw_status"),      ← openclaw-gateway.service is-active + HTTP :18789
  │  ])
  │
  ├─ applyBackendStatus(info)   → updates #backend-dot, #backend-state-text,
  │                                #backend-http-indicator, btn-backend-{start,stop,restart}
  │
  ├─ applyFrontendStatus(info)  → updates #frontend-dot, #frontend-state-text,
  │                                #frontend-http-indicator, btn-frontend-{start,stop,restart},
  │                                btn-link-jarvis (disabled when !http_ok)
  │
  └─ applyOpenclawStatus(info)  → unchanged from today

Button click (e.g. btn-frontend-start)
  → invoke("start_frontend")
  → lib.rs: run_systemctl(["--user", "start", "jarvis-frontend.service"])
  → systemd spawns: npm run dev  (WorkingDirectory = /home/paps/Repos/Jarvis/frontend)
  → Vite binds :5173
  → Next poll: frontend_status returns state="active", http_ok=true
  → UI updates accordingly
```

### Interfaces

#### Rust — `controller/src-tauri/src/lib.rs`

New private helper:
```
async fn check_http_frontend() -> bool
  // GET http://127.0.0.1:5173/ with 500 ms timeout; true on any HTTP response (2xx or otherwise).
  // Vite returns 200 for its root; an HTTP response at all is sufficient proof the server is up.
```

New public Tauri commands (all in `pub mod commands`):
```
#[tauri::command]
pub async fn restart_jarvis() -> Result<String, String>
  // run_systemctl(&["--user", "restart", "jarvis-backend.service"])

#[tauri::command]
pub async fn start_frontend() -> Result<String, String>
  // run_systemctl(&["--user", "start", "jarvis-frontend.service"])

#[tauri::command]
pub async fn stop_frontend() -> Result<String, String>
  // run_systemctl(&["--user", "stop", "jarvis-frontend.service"])

#[tauri::command]
pub async fn restart_frontend() -> Result<String, String>
  // run_systemctl(&["--user", "restart", "jarvis-frontend.service"])

#[tauri::command]
pub async fn frontend_status() -> Result<StatusInfo, String>
  // systemctl --user is-active jarvis-frontend.service → state
  // check_http_frontend() → http_ok
  // Returns StatusInfo { state, http_ok }
```

Updated `tauri::generate_handler!` registration — must include all five new commands plus the existing six.

#### HTML — `controller/index.html`

New DOM structure inside the JARVIS `.service-card` (replaces the single flat `status-section` + `controls`):

```
<div class="service-card">
  <div class="service-label">JARVIS</div>

  <!-- Backend sub-row -->
  <div class="sub-service">
    <div class="sub-service-label">BACKEND</div>
    <section class="status-section">
      <div class="status-pill" id="backend-status-pill">
        <span class="dot" id="backend-dot"></span>
        <span class="state-text" id="backend-state-text">checking...</span>
      </div>
      <div class="http-indicator" id="backend-http-indicator">HTTP :8766 · checking</div>
    </section>
    <section class="controls">
      <button class="btn btn-start"   id="btn-backend-start"   disabled>START</button>
      <button class="btn btn-stop"    id="btn-backend-stop"    disabled>STOP</button>
      <button class="btn btn-restart" id="btn-backend-restart" disabled>RESTART</button>
    </section>
  </div>

  <!-- Frontend sub-row -->
  <div class="sub-service">
    <div class="sub-service-label">FRONTEND</div>
    <section class="status-section">
      <div class="status-pill" id="frontend-status-pill">
        <span class="dot" id="frontend-dot"></span>
        <span class="state-text" id="frontend-state-text">checking...</span>
      </div>
      <div class="http-indicator" id="frontend-http-indicator">HTTP :5173 · checking</div>
    </section>
    <section class="controls">
      <button class="btn btn-start"   id="btn-frontend-start"   disabled>START</button>
      <button class="btn btn-stop"    id="btn-frontend-stop"    disabled>STOP</button>
      <button class="btn btn-restart" id="btn-frontend-restart" disabled>RESTART</button>
    </section>
    <button class="btn btn-link" id="btn-link-jarvis" disabled>Open JARVIS UI →</button>
  </div>
</div>
```

The `btn-link-jarvis` moves from the bottom `links-row` into the frontend sub-row. If only the OpenClaw link remains, the `links-row` section shrinks to a single button — that is acceptable; do not delete `links-row` in CSS (OpenClaw still uses it).

**Rationale for absorbing the link into the frontend sub-row:** the link is semantically part of the frontend service, not a top-level navigation item. Gating it on `http_ok` without needing a separate code path is cleaner. The proximity also makes the causal relationship (service up → link clickable) visually obvious.

#### TypeScript — `controller/src/main.ts`

Renamed DOM ref group: old `jarvis*` refs become `backend*` refs. New `frontend*` ref group added. New `applyBackendStatus` and `applyFrontendStatus` functions mirror existing pattern. `pollAll` extended with a third `Promise.allSettled` branch. Six new button event listeners (backend-restart, frontend-start, stop, restart). `btnLinkJarvis.disabled` toggled inside `applyFrontendStatus` based on `info.http_ok`.

Key new function signatures (no bodies):
```
function applyBackendStatus(info: StatusInfo): void
function applyFrontendStatus(info: StatusInfo): void
```

`StatusInfo` interface is unchanged.

#### CSS — `controller/src/style.css`

New rules only — existing rules untouched:
```
.sub-service          /* flex column, gap 20px, width 100%, border-top separator */
.sub-service-label    /* font-size 11px, letter-spacing 0.22em, color var(--text-muted), uppercase */
```

The `.sub-service-label` uses a smaller text than `.service-label` to establish visual hierarchy (card title > sub-row label > state text).

#### systemd unit — `ops/jarvis-frontend.service`

```ini
[Unit]
Description=JARVIS Frontend (Vite dev server, :5173)
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/paps/Repos/Jarvis/frontend
Environment="PATH=/home/paps/.nvm/versions/node/v24.15.0/bin:/home/paps/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=/home/paps/.nvm/versions/node/v24.15.0/bin/npm run dev
Restart=always
RestartSec=3
StandardOutput=append:/tmp/jarvis-frontend.log
StandardError=append:/tmp/jarvis-frontend.log

[Install]
WantedBy=default.target
```

Notes on this unit:
- `ExecStart` uses the absolute path to `npm` from the nvm-managed node installation — same convention as the backend service's PATH. Using an absolute path avoids relying on `PATH` expansion in `ExecStart` for the primary binary.
- `After=network.target` only (not `openclaw-gateway.service`) — the frontend has no runtime dependency on OpenClaw at startup.
- `WantedBy=default.target` mirrors the backend unit; the unit does NOT auto-start unless the user explicitly runs `systemctl --user enable jarvis-frontend.service`.
- The node version path (`v24.15.0`) must match the version in `jarvis-backend.service`. If that version changes, both files must be updated in lockstep — flag this in a comment inside the unit.

**One-time installation steps (must be documented in the unit file as a comment block and in a `## Installation` note):**
```
systemctl --user daemon-reload
# optionally:
systemctl --user enable jarvis-frontend.service
```

### External dependencies
- No new pip packages.
- No new npm packages for the controller frontend.
- No new Rust crates (uses existing `reqwest`, `tokio`, `tauri`).
- Requires `node` v24.15.0 (nvm) already present on the host — same constraint as the backend service.

## Edge Cases & Failure Modes

- **`node_modules` missing** — `npm run dev` exits immediately with a non-zero code; systemd marks the unit `failed`. The status dot shows `failed`, state text shows "failed". The user must run `npm install` inside `frontend/` manually. No silent degradation — the failed state is visible in the controller.
- **Port 5173 already in use** — Vite fails on startup, unit enters `failed` state. HTTP probe on :5173 may return an unexpected response (from whatever process owns the port), causing `http_ok=true` while the unit is `failed`. The spec requires the UI to show the systemd state (failed) as the authoritative signal; `http_ok` is supplementary. Button disable logic must be driven by systemd state, not HTTP probe alone.
- **User runs `npm run dev` manually while the service is also started** — port conflict; the service unit fails (Vite process already bound to :5173). The manually started Vite keeps running and the HTTP probe stays true, but systemd state shows `failed`. This is a user error; document it in the unit as a warning comment.
- **Vite initial cold start (first-time compilation)** — Vite can take 3–8 seconds on a cold cache before binding :5173. During this window: systemd state = `activating`, HTTP probe = `false`. The Restart button must remain disabled while `activating`. Do not spam restart during this window.
- **Restart flapping** — if the HTTP probe stays false after restart (e.g. stuck activating), the UI does not automatically retry — it just reflects what systemd reports. No automatic retry logic in the controller.
- **Backend restart during active voice session** — `restart_jarvis` is a hard systemctl restart; any in-flight WebSocket connections to the backend are dropped. This is expected and documented — no graceful drain is implemented in this feature.
- **systemd not available** — `run_systemctl` returns an error string; the Tauri command returns `Err(...)`, `main.ts` catches it and shows "error" in the state text. This is the same behaviour as existing commands.
- **Tauri invoke timeout** — Tauri has no built-in command timeout. The `systemctl` call and HTTP probe both have at most a few hundred ms of OS overhead. If systemd hangs (very rare), the poll tick simply takes longer; the UI freezes for that tick only. No additional guard needed for this feature.
- **nvm node path mismatch** — if the user upgrades node via nvm and the path in the unit file is stale, `ExecStart` fails immediately with "No such file or directory". Unit enters `failed` state. Same failure mode as `jarvis-backend.service` today — not introduced by this feature, but the unit file comment should warn about it.
- **Controller window too small to fit two sub-rows** — the JARVIS card will be taller than the OpenClaw card. The `services-grid` uses `align-items: start` so the two cards do not stretch to equal height; the JARVIS card will simply be taller. No scrolling required at default window size (verify during manual verification).

## Acceptance Criteria

1. `ops/jarvis-frontend.service` exists, passes `systemd-analyze verify ops/jarvis-frontend.service` with no errors.
2. After `systemctl --user daemon-reload && systemctl --user start jarvis-frontend.service`, `systemctl --user status jarvis-frontend.service` shows `active (running)` within 15 seconds, and `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5173/` returns 200.
3. After `systemctl --user stop jarvis-frontend.service`, the frontend sub-row status dot transitions to the inactive/grey state within the next 2-second poll tick.
4. The JARVIS card displays two labelled sub-rows ("BACKEND" and "FRONTEND") with no visual overlap or layout breakage at the default controller window size.
5. The Backend sub-row has exactly three buttons: START, STOP, RESTART.
6. The Frontend sub-row has exactly three buttons: START, STOP, RESTART, plus the "Open JARVIS UI →" link button.
7. The START button in each sub-row is disabled when the service state is `active` or `activating`; STOP and RESTART are disabled when state is `inactive` or `failed`.
8. `invoke("restart_jarvis")` from the Tauri dev console executes `systemctl --user restart jarvis-backend.service` (verify via `journalctl --user -u jarvis-backend.service -n 5` showing a restart event).
9. `invoke("restart_frontend")` executes `systemctl --user restart jarvis-frontend.service` (same verification method).
10. The "Open JARVIS UI →" button is disabled (HTML `disabled` attribute set) when `frontend_status.http_ok` is `false`, and enabled when `http_ok` is `true`.
11. Clicking "Open JARVIS UI →" while enabled opens `http://localhost:5173` in the system browser (observable: browser tab appears).
12. The bottom `links-row` retains only the "Open OpenClaw Control →" button; the JARVIS UI link is no longer present there.
13. All three services (backend, frontend, openclaw) are polled in parallel every 2 seconds with no serial blocking — confirm by adding a `console.time`/`console.timeEnd` around `pollAll` and observing that total poll duration is bounded by the slowest single probe, not their sum.
14. A toast appears within 1 second of clicking any action button (start/stop/restart for either JARVIS sub-row), confirming success or displaying the error message returned by the Tauri command.
15. Vitest test suite passes with `npm run test` inside `controller/` (or wherever tests live) with no failures.
16. The controller Tauri app builds successfully with `cargo tauri build` (or `npm run tauri build`) after all changes.

## Implementation Plan

1. `backend-dev` → create `ops/jarvis-frontend.service` following the unit conventions above; include inline comment block explaining the nvm path, the one-time daemon-reload step, and the port-conflict warning.
2. `backend-dev` → add `check_http_frontend()` private helper to `controller/src-tauri/src/lib.rs` mirroring `check_http_jarvis()` but probing `http://127.0.0.1:5173/`.
3. `backend-dev` → add `restart_jarvis`, `start_frontend`, `stop_frontend`, `restart_frontend`, `frontend_status` commands to `pub mod commands` in `controller/src-tauri/src/lib.rs`; register all five in `tauri::generate_handler!`.
4. `frontend-dev` → restructure the JARVIS `.service-card` in `controller/index.html` into two `.sub-service` rows with the exact IDs specified in the Interfaces section; move `btn-link-jarvis` into the frontend sub-row; shrink `links-row` to OpenClaw link only.
5. `frontend-dev` → add `.sub-service` and `.sub-service-label` CSS rules to `controller/src/style.css`; no changes to existing rules.
6. `frontend-dev` → rewrite JARVIS-related wiring in `controller/src/main.ts`: rename `jarvis*` DOM refs to `backend*`; add `frontend*` DOM refs; implement `applyBackendStatus` and `applyFrontendStatus`; add `frontend_status` to `pollAll`; add event listeners for `btn-backend-restart`, `btn-frontend-start`, `btn-frontend-stop`, `btn-frontend-restart`; gate `btnLinkJarvis.disabled` on `info.http_ok` inside `applyFrontendStatus`.
7. `tester` → write Vitest tests for `controller/src/main.ts`: (a) `applyBackendStatus` with state="active" disables START and enables STOP/RESTART; (b) `applyFrontendStatus` with `http_ok=false` sets `btnLinkJarvis.disabled=true`; (c) `applyFrontendStatus` with `http_ok=true` sets `btnLinkJarvis.disabled=false`; (d) `pollAll` calls all three `invoke` variants. Mock `@tauri-apps/api/core` and `@tauri-apps/plugin-opener`.
8. `tester` → write Rust unit tests in `controller/src-tauri/src/lib.rs` (or a `tests/` module) for `check_http_frontend` and `frontend_status` using `mockito` or a local HTTP stub where feasible; at minimum test that the function constructs the correct systemctl args.
9. `reviewer` → review all deliverables from steps 1–8 against this spec; verify acceptance criteria 1–16; issue `PASS` or `NEEDS_CHANGES` with file-level feedback.

## Manual Verification

```bash
# 1. Install the new service unit
cp ops/jarvis-frontend.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user status jarvis-frontend.service   # should show "inactive (dead)"

# 2. Start via systemd
systemctl --user start jarvis-frontend.service
sleep 10
systemctl --user status jarvis-frontend.service   # active (running)
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5173/  # 200

# 3. Open the Tauri controller in dev mode
cd controller && npm run tauri dev

# 4. Observe the JARVIS card: two sub-rows visible, BACKEND and FRONTEND
# 5. Frontend sub-row dot should be active (blue glow); "Open JARVIS UI →" enabled
# 6. Click STOP on frontend sub-row → dot dims; link button disables
# 7. Click START on frontend sub-row → toast appears; dot activates after ~5s
# 8. Click RESTART on backend sub-row → backend restarts; journalctl confirms
#    journalctl --user -u jarvis-backend.service -n 5 --no-pager
# 9. Verify "Open OpenClaw Control →" still works in links-row
# 10. Resize controller window to minimum; verify no layout overflow
```

## Open Questions

1. **nvm node version hardcoding** — `ops/jarvis-frontend.service` uses the path `/home/paps/.nvm/versions/node/v24.15.0/bin/npm`. Should this be parameterised (e.g. a wrapper script that resolves the current nvm default) to survive a node upgrade, or is the hardcoded path acceptable (same policy as `jarvis-backend.service`)? Current recommendation: keep it hardcoded for consistency with the backend service; document the upgrade procedure in the unit comment.
2. **Dev vs. preview mode** — the spec defaults to `npm run dev` (hot-reload Vite dev server). If the user prefers a production-built frontend served via `npm run preview` (no hot reload, but lower RAM, no Vite overhead), the service unit's `ExecStart` line changes to `npm run preview` and `WorkingDirectory` may need a `dist/` pre-build step. This is deferred; confirm with the user before implementing if they prefer preview mode.
3. **HTTP probe on Vite returning non-2xx** — Vite's dev server root (`/`) returns 200 under normal operation. The `check_http_url` helper in `lib.rs` currently requires a 2xx status (`resp.status().is_success()`). For the frontend probe (`check_http_frontend`), a 200 is expected, but should the probe accept any HTTP response (i.e. "TCP port is open and speaking HTTP") rather than strictly 2xx? Recommendation: keep 2xx for consistency with other probes; Vite always returns 200 for its root.
4. **Tauri window height** — after adding two sub-rows to the JARVIS card the window may need to be taller. The current `tauri.conf.json` window height is not checked in this spec. The frontend-dev agent should inspect `controller/src-tauri/tauri.conf.json` and adjust `height` if the new card layout clips at the default size.
5. **Test location for controller Vitest** — the controller's `package.json` and `tsconfig.json` are at `controller/`, not the repo root. Confirm that a `tests/` or `src/__tests__/` directory inside `controller/` is the right location, or whether to co-locate test files as `main.test.ts` alongside `main.ts` in `controller/src/`. The tester agent should follow the existing test file convention in the controller (currently none exist — establish the convention and document it).
