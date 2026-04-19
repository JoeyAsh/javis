import { invoke } from "@tauri-apps/api/core";
import { openUrl } from "@tauri-apps/plugin-opener";

interface StatusInfo {
  state: string;
  http_ok: boolean;
}

// ── DOM refs — JARVIS ────────────────────────────────────────────────────────
const jarvisDot          = document.getElementById("jarvis-dot")           as HTMLSpanElement;
const jarvisStateText    = document.getElementById("jarvis-state-text")    as HTMLSpanElement;
const jarvisHttpIndicator= document.getElementById("jarvis-http-indicator")as HTMLDivElement;
const btnJarvisStart     = document.getElementById("btn-jarvis-start")     as HTMLButtonElement;
const btnJarvisStop      = document.getElementById("btn-jarvis-stop")      as HTMLButtonElement;

// ── DOM refs — OpenClaw ──────────────────────────────────────────────────────
const openclawDot          = document.getElementById("openclaw-dot")           as HTMLSpanElement;
const openclawStateText    = document.getElementById("openclaw-state-text")    as HTMLSpanElement;
const openclawHttpIndicator= document.getElementById("openclaw-http-indicator")as HTMLDivElement;
const btnOpenclawStart     = document.getElementById("btn-openclaw-start")     as HTMLButtonElement;
const btnOpenclawStop      = document.getElementById("btn-openclaw-stop")      as HTMLButtonElement;
const btnOpenclawRestart   = document.getElementById("btn-openclaw-restart")   as HTMLButtonElement;

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
  } else {
    dot.classList.add("unknown");
  }
}

function applyJarvisStatus(info: StatusInfo): void {
  const state = info.state.toLowerCase().trim();
  applyDot(jarvisDot, state);
  jarvisStateText.textContent = state;

  jarvisHttpIndicator.textContent = `HTTP :8766 · ${info.http_ok ? "reachable" : "unreachable"}`;
  jarvisHttpIndicator.className = "http-indicator " + (info.http_ok ? "reachable" : "unreachable");

  const isRunning = state === "active" || state === "activating";
  const isStopped = state === "inactive" || state === "failed";
  btnJarvisStart.disabled = isRunning;
  btnJarvisStop.disabled  = isStopped;
}

function applyOpenclawStatus(info: StatusInfo): void {
  const state = info.state.toLowerCase().trim();
  applyDot(openclawDot, state);
  openclawStateText.textContent = state;

  openclawHttpIndicator.textContent = `HTTP :18789 · ${info.http_ok ? "reachable" : "unreachable"}`;
  openclawHttpIndicator.className = "http-indicator " + (info.http_ok ? "reachable" : "unreachable");

  const isRunning = state === "active" || state === "activating";
  const isStopped = state === "inactive" || state === "failed";
  btnOpenclawStart.disabled   = isRunning;
  btnOpenclawStop.disabled    = isStopped;
  btnOpenclawRestart.disabled = isStopped;
}

// ── Polling ───────────────────────────────────────────────────────────────────
async function pollAll(): Promise<void> {
  // Poll both services in parallel; errors are independent
  await Promise.allSettled([
    (async () => {
      try {
        const info = await invoke<StatusInfo>("jarvis_status");
        applyJarvisStatus(info);
      } catch (e) {
        jarvisStateText.textContent = "error";
        jarvisDot.className = "dot unknown";
        console.error("jarvis status poll failed:", e);
      }
    })(),
    (async () => {
      try {
        const info = await invoke<StatusInfo>("openclaw_status");
        applyOpenclawStatus(info);
      } catch (e) {
        openclawStateText.textContent = "error";
        openclawDot.className = "dot unknown";
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

// ── JARVIS button handlers ────────────────────────────────────────────────────
btnJarvisStart.addEventListener("click", async () => {
  btnJarvisStart.disabled = true;
  stopPolling();
  try {
    await invoke<string>("start_jarvis");
    showToast(`jarvis · started · ${timestamp()}`);
  } catch (e) {
    const msg = typeof e === "string" ? e : String(e);
    showToast(`jarvis · start failed: ${msg}`, true);
  }
  setTimeout(async () => { await pollAll(); startPolling(); }, 300);
});

btnJarvisStop.addEventListener("click", async () => {
  btnJarvisStop.disabled = true;
  stopPolling();
  try {
    await invoke<string>("stop_jarvis");
    showToast(`jarvis · stopped · ${timestamp()}`);
  } catch (e) {
    const msg = typeof e === "string" ? e : String(e);
    showToast(`jarvis · stop failed: ${msg}`, true);
  }
  setTimeout(async () => { await pollAll(); startPolling(); }, 300);
});

// ── OpenClaw button handlers ──────────────────────────────────────────────────
btnOpenclawStart.addEventListener("click", async () => {
  btnOpenclawStart.disabled = true;
  stopPolling();
  try {
    await invoke<string>("start_openclaw");
    showToast(`openclaw · started · ${timestamp()}`);
  } catch (e) {
    const msg = typeof e === "string" ? e : String(e);
    showToast(`openclaw · start failed: ${msg}`, true);
  }
  setTimeout(async () => { await pollAll(); startPolling(); }, 300);
});

btnOpenclawStop.addEventListener("click", async () => {
  btnOpenclawStop.disabled = true;
  stopPolling();
  try {
    await invoke<string>("stop_openclaw");
    showToast(`openclaw · stopped · ${timestamp()}`);
  } catch (e) {
    const msg = typeof e === "string" ? e : String(e);
    showToast(`openclaw · stop failed: ${msg}`, true);
  }
  setTimeout(async () => { await pollAll(); startPolling(); }, 300);
});

btnOpenclawRestart.addEventListener("click", async () => {
  btnOpenclawRestart.disabled = true;
  stopPolling();
  try {
    await invoke<string>("restart_openclaw");
    showToast(`openclaw · restarted · ${timestamp()}`);
  } catch (e) {
    const msg = typeof e === "string" ? e : String(e);
    showToast(`openclaw · restart failed: ${msg}`, true);
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

// ── Boot ──────────────────────────────────────────────────────────────────────
pollAll().then(() => startPolling());
