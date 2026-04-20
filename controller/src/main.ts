import { invoke } from "@tauri-apps/api/core";
import { openUrl } from "@tauri-apps/plugin-opener";

interface StatusInfo {
  state: string;
  http_ok: boolean;
}

interface OpenclawTargetInfo {
  target: string;
  url: string;
}

// ── DOM refs — Backend (JARVIS backend service) ───────────────────────────────
const backendDot           = document.getElementById("backend-dot")           as HTMLSpanElement;
const backendStateText     = document.getElementById("backend-state-text")    as HTMLSpanElement;
const backendHttpIndicator = document.getElementById("backend-http-indicator")as HTMLDivElement;
const btnBackendStart      = document.getElementById("btn-backend-start")     as HTMLButtonElement;
const btnBackendStop       = document.getElementById("btn-backend-stop")      as HTMLButtonElement;
const btnBackendRestart    = document.getElementById("btn-backend-restart")   as HTMLButtonElement;

// ── DOM refs — Frontend (JARVIS frontend service) ─────────────────────────────
const frontendDot           = document.getElementById("frontend-dot")           as HTMLSpanElement;
const frontendStateText     = document.getElementById("frontend-state-text")    as HTMLSpanElement;
const frontendHttpIndicator = document.getElementById("frontend-http-indicator")as HTMLDivElement;
const btnFrontendStart      = document.getElementById("btn-frontend-start")     as HTMLButtonElement;
const btnFrontendStop       = document.getElementById("btn-frontend-stop")      as HTMLButtonElement;
const btnFrontendRestart    = document.getElementById("btn-frontend-restart")   as HTMLButtonElement;

// ── DOM refs — OpenClaw ──────────────────────────────────────────────────────
const openclawDot          = document.getElementById("openclaw-dot")           as HTMLSpanElement;
const openclawStateText    = document.getElementById("openclaw-state-text")    as HTMLSpanElement;
const openclawHttpIndicator= document.getElementById("openclaw-http-indicator")as HTMLDivElement;
const btnOpenclawStart     = document.getElementById("btn-openclaw-start")     as HTMLButtonElement;
const btnOpenclawStop      = document.getElementById("btn-openclaw-stop")      as HTMLButtonElement;
const btnOpenclawRestart   = document.getElementById("btn-openclaw-restart")   as HTMLButtonElement;
const toggleLocal          = document.getElementById("toggle-local")           as HTMLButtonElement;
const toggleRemote         = document.getElementById("toggle-remote")          as HTMLButtonElement;
const openclawTargetUrl    = document.getElementById("openclaw-target-url")    as HTMLDivElement;

// ── DOM refs — links ─────────────────────────────────────────────────────────
const btnLinkJarvis   = document.getElementById("btn-link-jarvis")   as HTMLButtonElement;
const btnLinkOpenclaw = document.getElementById("btn-link-openclaw") as HTMLButtonElement;

// ── DOM refs — shared ────────────────────────────────────────────────────────
const toast = document.getElementById("toast") as HTMLDivElement;

// ── State ────────────────────────────────────────────────────────────────────
let toastTimer: ReturnType<typeof setTimeout> | null = null;
let pollInterval: ReturnType<typeof setInterval> | null = null;

// ── Toast ────────────────────────────────────────────────────────────────────
function showToast(message: string, isError = false): void {
  toast.textContent = message;
  toast.className = "toast visible" + (isError ? " error" : "");
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toast.className = "toast";
  }, 5000);
}

// ── Status helpers ────────────────────────────────────────────────────────────
function applyDot(dot: HTMLSpanElement, state: string): void {
  dot.className = "dot";
  if (state === "active") {
    dot.classList.add("active");
  } else if (state === "activating") {
    dot.classList.add("activating");
  } else if (state === "inactive") {
    dot.classList.add("inactive");
  } else if (state === "failed") {
    dot.classList.add("failed");
  } else if (state === "remote") {
    dot.classList.add("active");
  } else {
    dot.classList.add("unknown");
  }
}

/**
 * Derive button enable/disable state from a service state string.
 * Returns [startEnabled, stopEnabled, restartEnabled].
 * Rule:
 *   active / activating  → Start off, Stop+Restart on
 *   inactive / failed / unreachable → Start on, Stop+Restart off
 *   everything else (error, unknown, …) → Start on, Stop+Restart off (let user try)
 */
function serviceButtonState(state: string): [boolean, boolean, boolean] {
  if (state === "active" || state === "activating") {
    return [false, true, true];
  }
  // inactive, failed, unreachable, error, unknown, or anything else
  return [true, false, false];
}

function applyBackendStatus(info: StatusInfo): void {
  const state = info.state.toLowerCase().trim();
  applyDot(backendDot, state);
  backendStateText.textContent = state;

  backendHttpIndicator.textContent = `HTTP :8766 · ${info.http_ok ? "reachable" : "unreachable"}`;
  backendHttpIndicator.className = "http-indicator " + (info.http_ok ? "reachable" : "unreachable");

  const [startOn, stopOn, restartOn] = serviceButtonState(state);
  btnBackendStart.disabled   = !startOn;
  btnBackendStop.disabled    = !stopOn;
  btnBackendRestart.disabled = !restartOn;
}

function applyFrontendStatus(info: StatusInfo): void {
  const state = info.state.toLowerCase().trim();
  applyDot(frontendDot, state);
  frontendStateText.textContent = state;

  frontendHttpIndicator.textContent = `HTTP :5173 · ${info.http_ok ? "reachable" : "unreachable"}`;
  frontendHttpIndicator.className = "http-indicator " + (info.http_ok ? "reachable" : "unreachable");

  const [startOn, stopOn, restartOn] = serviceButtonState(state);
  btnFrontendStart.disabled   = !startOn;
  btnFrontendStop.disabled    = !stopOn;
  btnFrontendRestart.disabled = !restartOn;

  // Gate link button on HTTP probe only
  btnLinkJarvis.disabled = !info.http_ok;
}

function applyOpenclawStatus(info: StatusInfo): void {
  const state = info.state.toLowerCase().trim();
  applyDot(openclawDot, state);
  openclawStateText.textContent = state;

  openclawHttpIndicator.textContent = `HTTP · ${info.http_ok ? "reachable" : "unreachable"}`;
  openclawHttpIndicator.className = "http-indicator " + (info.http_ok ? "reachable" : "unreachable");

  // OpenClaw is always remote — all three action buttons stay disabled.
  // "Open…" link is enabled when reachable (state === "remote" / http_ok).
  btnOpenclawStart.disabled   = true;
  btnOpenclawStop.disabled    = true;
  btnOpenclawRestart.disabled = true;
  btnLinkOpenclaw.disabled    = !info.http_ok;
}

// ── Polling ───────────────────────────────────────────────────────────────────
async function pollAll(): Promise<void> {
  await Promise.allSettled([
    (async () => {
      try {
        const info = await invoke<StatusInfo>("jarvis_status");
        applyBackendStatus(info);
      } catch (e) {
        backendStateText.textContent = "error";
        backendDot.className = "dot unknown";
        // On error: let user attempt start; stop/restart make no sense
        btnBackendStart.disabled   = false;
        btnBackendStop.disabled    = true;
        btnBackendRestart.disabled = true;
        console.error("backend status poll failed:", e);
      }
    })(),
    (async () => {
      try {
        const info = await invoke<StatusInfo>("frontend_status");
        applyFrontendStatus(info);
      } catch (e) {
        frontendStateText.textContent = "error";
        frontendDot.className = "dot unknown";
        btnFrontendStart.disabled   = false;
        btnFrontendStop.disabled    = true;
        btnFrontendRestart.disabled = true;
        btnLinkJarvis.disabled      = true;
        console.error("frontend status poll failed:", e);
      }
    })(),
    (async () => {
      try {
        const info = await invoke<StatusInfo>("openclaw_status");
        applyOpenclawStatus(info);
      } catch (e) {
        openclawStateText.textContent = "error";
        openclawDot.className = "dot unknown";
        btnOpenclawStart.disabled   = true;
        btnOpenclawStop.disabled    = true;
        btnOpenclawRestart.disabled = true;
        btnLinkOpenclaw.disabled    = true;
        console.error("openclaw status poll failed:", e);
      }
    })(),
  ]);
}

function startPolling(): void {
  stopPolling();
  pollInterval = setInterval(pollAll, 2000);
}

function stopPolling(): void {
  if (pollInterval) {
    clearInterval(pollInterval);
    pollInterval = null;
  }
}

function timestamp(): string {
  return new Date().toLocaleTimeString("en-GB", { hour12: false });
}

// ── Backend button handlers ───────────────────────────────────────────────────
btnBackendStart.addEventListener("click", async () => {
  btnBackendStart.disabled = true;
  stopPolling();
  try {
    await invoke<string>("start_jarvis");
    showToast(`backend · started · ${timestamp()}`);
  } catch (e) {
    const msg = typeof e === "string" ? e : String(e);
    showToast(`backend · start failed: ${msg}`, true);
  }
  setTimeout(async () => { await pollAll(); startPolling(); }, 300);
});

btnBackendStop.addEventListener("click", async () => {
  btnBackendStop.disabled = true;
  stopPolling();
  try {
    await invoke<string>("stop_jarvis");
    showToast(`backend · stopped · ${timestamp()}`);
  } catch (e) {
    const msg = typeof e === "string" ? e : String(e);
    showToast(`backend · stop failed: ${msg}`, true);
  }
  setTimeout(async () => { await pollAll(); startPolling(); }, 300);
});

btnBackendRestart.addEventListener("click", async () => {
  btnBackendRestart.disabled = true;
  stopPolling();
  try {
    await invoke<string>("restart_jarvis");
    showToast(`backend · restarted · ${timestamp()}`);
  } catch (e) {
    const msg = typeof e === "string" ? e : String(e);
    showToast(`backend · restart failed: ${msg}`, true);
  }
  setTimeout(async () => { await pollAll(); startPolling(); }, 300);
});

// ── Frontend button handlers ──────────────────────────────────────────────────
btnFrontendStart.addEventListener("click", async () => {
  btnFrontendStart.disabled = true;
  stopPolling();
  try {
    await invoke<string>("start_frontend");
    showToast(`frontend · started · ${timestamp()}`);
  } catch (e) {
    const msg = typeof e === "string" ? e : String(e);
    showToast(`frontend · start failed: ${msg}`, true);
  }
  setTimeout(async () => { await pollAll(); startPolling(); }, 300);
});

btnFrontendStop.addEventListener("click", async () => {
  btnFrontendStop.disabled = true;
  stopPolling();
  try {
    await invoke<string>("stop_frontend");
    showToast(`frontend · stopped · ${timestamp()}`);
  } catch (e) {
    const msg = typeof e === "string" ? e : String(e);
    showToast(`frontend · stop failed: ${msg}`, true);
  }
  setTimeout(async () => { await pollAll(); startPolling(); }, 300);
});

btnFrontendRestart.addEventListener("click", async () => {
  btnFrontendRestart.disabled = true;
  stopPolling();
  try {
    await invoke<string>("restart_frontend");
    showToast(`frontend · restarted · ${timestamp()}`);
  } catch (e) {
    const msg = typeof e === "string" ? e : String(e);
    showToast(`frontend · restart failed: ${msg}`, true);
  }
  setTimeout(async () => { await pollAll(); startPolling(); }, 300);
});

// ── OpenClaw button handlers (remote — always show informative toast) ─────────
btnOpenclawStart.addEventListener("click", async () => {
  stopPolling();
  try {
    await invoke<string>("start_openclaw");
  } catch (e) {
    const msg = typeof e === "string" ? e : String(e);
    showToast(`openclaw · ${msg}`, true);
  }
  setTimeout(async () => { await pollAll(); startPolling(); }, 300);
});

btnOpenclawStop.addEventListener("click", async () => {
  stopPolling();
  try {
    await invoke<string>("stop_openclaw");
  } catch (e) {
    const msg = typeof e === "string" ? e : String(e);
    showToast(`openclaw · ${msg}`, true);
  }
  setTimeout(async () => { await pollAll(); startPolling(); }, 300);
});

btnOpenclawRestart.addEventListener("click", async () => {
  stopPolling();
  try {
    await invoke<string>("restart_openclaw");
  } catch (e) {
    const msg = typeof e === "string" ? e : String(e);
    showToast(`openclaw · ${msg}`, true);
  }
  setTimeout(async () => { await pollAll(); startPolling(); }, 300);
});

// ── Link button handlers ──────────────────────────────────────────────────────
btnLinkJarvis.addEventListener("click", async () => {
  try {
    await openUrl("http://localhost:5173");
  } catch (e) {
    console.error("failed to open JARVIS UI:", e);
    showToast("failed to open browser", true);
  }
});

btnLinkOpenclaw.addEventListener("click", async () => {
  try {
    const url = await invoke<string>("openclaw_url");
    await openUrl(url);
  } catch (e) {
    console.error("failed to open OpenClaw Control:", e);
    showToast("failed to open browser", true);
  }
});

// ── OpenClaw target toggle ────────────────────────────────────────────────────
function applyOpenclawTarget(info: OpenclawTargetInfo): void {
  const isLocal = info.target === "local";
  toggleLocal.classList.toggle("active", isLocal);
  toggleRemote.classList.toggle("active", !isLocal);
  openclawTargetUrl.textContent = `Target: ${info.url}`;
}

async function initOpenclawTargetToggle(): Promise<void> {
  try {
    const info = await invoke<OpenclawTargetInfo>("get_openclaw_target");
    applyOpenclawTarget(info);
  } catch (e) {
    openclawTargetUrl.textContent = "Target: unknown";
    console.error("get_openclaw_target failed:", e);
  }
}

async function handleTargetSelect(target: "local" | "remote"): Promise<void> {
  const currentlyActive = target === "local"
    ? toggleLocal.classList.contains("active")
    : toggleRemote.classList.contains("active");
  if (currentlyActive) return;

  try {
    const info = await invoke<OpenclawTargetInfo>("set_openclaw_target", { target });
    applyOpenclawTarget(info);
    showToast(`openclaw · target = ${target} · restart backend to apply`);
  } catch (e) {
    const msg = typeof e === "string" ? e : String(e);
    showToast(`openclaw · set target failed: ${msg}`, true);
  }
}

toggleLocal.addEventListener("click", () => handleTargetSelect("local"));
toggleRemote.addEventListener("click", () => handleTargetSelect("remote"));

// ── Boot ──────────────────────────────────────────────────────────────────────
initOpenclawTargetToggle();
pollAll().then(() => startPolling());
