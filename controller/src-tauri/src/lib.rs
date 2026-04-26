use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::LazyLock;
use std::time::Duration;
use tokio::process::Child;
use tokio::sync::Mutex;

#[derive(Debug, Serialize, Deserialize)]
pub struct StatusInfo {
    pub state: String,
    pub http_ok: bool,
}

// ── Settings store ────────────────────────────────────────────────────────────

/// Serialised shape of `settings.json`.
#[derive(Debug, Serialize, Deserialize)]
struct OpenclawSettings {
    openclaw: OpenclawSection,
}

#[derive(Debug, Serialize, Deserialize)]
struct OpenclawSection {
    /// `"local"` or `"remote"`.
    target: String,
    /// LAN/tailnet URL of the remote OpenClaw gateway.
    /// For Tailscale setups: `http://<tailscale-ip>:18789`
    /// For local OpenClaw: `http://127.0.0.1:18789`
    #[serde(default = "default_remote_url")]
    remote_url: String,
    // NOTE: `ssh_host` was removed — SSH-tunnel management is no longer part of the
    // Controller. Remote access is now handled by Tailscale. Old settings files that
    // still contain `ssh_host` are silently ignored via serde's unknown-field handling.
}

fn default_remote_url() -> String {
    "http://192.168.1.121:18789".into()
}

/// Response type exposed to the frontend via Tauri commands.
#[derive(Debug, Serialize)]
pub struct OpenclawTargetInfo {
    /// `"local"` or `"remote"`.
    pub target: String,
    /// The resolved base URL for that target.
    pub url: String,
    /// Configured remote URL (Tailscale or LAN address of the gateway).
    pub remote_url: String,
}

/// Return the OS-standard user-config path for `jarvis-controller/settings.json`.
///
/// - Windows  : `%APPDATA%\jarvis-controller\settings.json`
/// - macOS    : `~/Library/Application Support/jarvis-controller/settings.json`
/// - Linux    : `~/.config/jarvis-controller/settings.json`
fn settings_path() -> PathBuf {
    #[cfg(target_os = "windows")]
    let base = std::env::var("APPDATA")
        .unwrap_or_else(|_| "C:\\Users\\user\\AppData\\Roaming".into());

    #[cfg(target_os = "macos")]
    let base = {
        let home = std::env::var("HOME").unwrap_or_else(|_| "/root".into());
        format!("{}/Library/Application Support", home)
    };

    #[cfg(target_os = "linux")]
    let base = {
        let home = std::env::var("HOME").unwrap_or_else(|_| "/root".into());
        format!("{}/.config", home)
    };

    PathBuf::from(base)
        .join("jarvis-controller")
        .join("settings.json")
}

/// Read the persisted OpenClaw settings.
/// Returns defaults whenever the file is missing or contains invalid JSON.
fn read_openclaw_settings() -> OpenclawSection {
    let path = settings_path();
    let contents = match std::fs::read_to_string(&path) {
        Ok(c) => c,
        Err(_) => {
            return OpenclawSection {
                target: "remote".into(),
                remote_url: default_remote_url(),
            }
        }
    };
    let settings: OpenclawSettings = match serde_json::from_str(&contents) {
        Ok(s) => s,
        Err(_) => {
            return OpenclawSection {
                target: "remote".into(),
                remote_url: default_remote_url(),
            }
        }
    };
    let target = match settings.openclaw.target.as_str() {
        "local" | "remote" => settings.openclaw.target,
        _ => "remote".into(),
    };
    OpenclawSection {
        target,
        remote_url: settings.openclaw.remote_url,
    }
}

/// Persist the OpenClaw settings.
/// Creates the config directory if it does not yet exist.
fn write_openclaw_settings(section: &OpenclawSection) -> Result<(), String> {
    let path = settings_path();
    if let Some(dir) = path.parent() {
        std::fs::create_dir_all(dir)
            .map_err(|e| format!("cannot create settings dir: {e}"))?;
    }
    let settings = OpenclawSettings {
        openclaw: OpenclawSection {
            target: section.target.clone(),
            remote_url: section.remote_url.clone(),
        },
    };
    let json = serde_json::to_string_pretty(&settings)
        .map_err(|e| format!("cannot serialise settings: {e}"))?;
    std::fs::write(&path, json).map_err(|e| format!("cannot write settings: {e}"))
}

/// Build an `OpenclawTargetInfo` from a settings section, computing `url` the
/// same way `openclaw_base_url()` does.
fn to_info(s: &OpenclawSection) -> OpenclawTargetInfo {
    let url = match s.target.as_str() {
        "local" => "http://127.0.0.1:18789".into(),
        "remote" => s.remote_url.clone(),
        _ => "http://127.0.0.1:18789".into(),
    };
    OpenclawTargetInfo {
        target: s.target.clone(),
        url,
        remote_url: s.remote_url.clone(),
    }
}

// ── Repo-root detection ───────────────────────────────────────────────────────

/// Resolve the JARVIS repo root.
/// Order: `JARVIS_REPO_ROOT` env var → walk up from current exe looking for
/// `config/config.yaml` → error.
fn repo_root() -> Result<PathBuf, String> {
    if let Ok(v) = std::env::var("JARVIS_REPO_ROOT") {
        return Ok(PathBuf::from(v));
    }

    let exe = std::env::current_exe()
        .map_err(|e| format!("cannot resolve exe path: {e}"))?;

    let mut dir = exe.as_path();
    loop {
        if dir.join("config").join("config.yaml").exists() {
            return Ok(dir.to_path_buf());
        }
        match dir.parent() {
            Some(p) => dir = p,
            None => break,
        }
    }

    Err("Could not detect JARVIS repo root. Set JARVIS_REPO_ROOT env var.".into())
}

// ── Config helpers ────────────────────────────────────────────────────────────

/// Resolve the OpenClaw base URL.
///
/// Precedence:
/// 1. `JARVIS_OPENCLAW_URL` env var (explicit override).
/// 2. Settings file `target`: `"local"` → `http://127.0.0.1:18789`,
///    `"remote"` → the configured `remote_url` field (Tailscale or LAN URL).
/// 3. Hardcoded fallback `http://127.0.0.1:18789`.
fn openclaw_base_url() -> String {
    if let Ok(v) = std::env::var("JARVIS_OPENCLAW_URL") {
        if !v.trim().is_empty() {
            return v;
        }
    }
    let s = read_openclaw_settings();
    match s.target.as_str() {
        "local" => "http://127.0.0.1:18789".into(),
        "remote" => s.remote_url,
        _ => "http://127.0.0.1:18789".into(),
    }
}

// ── HTTP probes ───────────────────────────────────────────────────────────────

async fn check_http_url(url: &str) -> bool {
    let client = match reqwest::Client::builder()
        .timeout(Duration::from_millis(500))
        .build()
    {
        Ok(c) => c,
        Err(_) => return false,
    };
    match client.get(url).send().await {
        Ok(resp) => resp.status().is_success(),
        Err(_) => false,
    }
}

async fn check_http_jarvis() -> bool {
    check_http_url("http://127.0.0.1:8766/health").await
}

async fn check_http_frontend() -> bool {
    check_http_url("http://127.0.0.1:5173/").await
}

async fn check_http_openclaw() -> bool {
    let base = openclaw_base_url();
    let url = format!("{}/", base.trim_end_matches('/'));
    check_http_url(&url).await
}

// ── Process tracker (Windows / macOS) ────────────────────────────────────────

#[cfg(not(target_os = "linux"))]
static CHILDREN: LazyLock<Mutex<HashMap<&'static str, Child>>> =
    LazyLock::new(|| Mutex::new(HashMap::new()));

/// Possible exit status of a tracked child.
#[cfg(not(target_os = "linux"))]
#[derive(Debug, Clone, Copy, PartialEq)]
enum ChildState {
    /// Still running (try_wait returned Ok(None)).
    Running,
    /// Exited successfully.
    Exited,
    /// Exited with non-zero code.
    Failed,
    /// Not in the map.
    NotTracked,
}

#[cfg(not(target_os = "linux"))]
async fn child_state(key: &'static str) -> ChildState {
    let mut map = CHILDREN.lock().await;
    match map.get_mut(key) {
        None => ChildState::NotTracked,
        Some(child) => match child.try_wait() {
            Ok(None) => ChildState::Running,
            Ok(Some(status)) => {
                map.remove(key);
                if status.success() {
                    ChildState::Exited
                } else {
                    ChildState::Failed
                }
            }
            Err(_) => {
                map.remove(key);
                ChildState::Failed
            }
        },
    }
}

// ── Command builders (Windows / macOS) ───────────────────────────────────────

#[cfg(not(target_os = "linux"))]
fn build_backend_command(repo: &PathBuf) -> tokio::process::Command {
    use std::process::Stdio;

    #[cfg(target_os = "windows")]
    let python = repo.join(".venv").join("Scripts").join("python.exe");
    #[cfg(not(target_os = "windows"))]
    let python = repo.join(".venv").join("bin").join("python");

    let mut cmd = tokio::process::Command::new(&python);
    cmd.args(["-m", "main"]);
    cmd.current_dir(repo);
    cmd.env("PYTHONPATH", repo.join("src"));
    cmd.env("OPENCLAW_GATEWAY_URL", openclaw_base_url());
    cmd.stdin(Stdio::null());
    cmd.stdout(Stdio::null());
    cmd.stderr(Stdio::null());

    #[cfg(target_os = "windows")]
    {
        // CREATE_NO_WINDOW so no console pops up
        use std::os::windows::process::CommandExt;
        cmd.creation_flags(0x08000000);
    }

    cmd
}

#[cfg(not(target_os = "linux"))]
fn build_frontend_command(repo: &PathBuf) -> tokio::process::Command {
    use std::process::Stdio;

    #[cfg(target_os = "windows")]
    let npm = "npm.cmd";
    #[cfg(not(target_os = "windows"))]
    let npm = "npm";

    let mut cmd = tokio::process::Command::new(npm);
    cmd.args(["run", "dev"]);
    cmd.current_dir(repo.join("frontend"));
    cmd.stdin(Stdio::null());
    cmd.stdout(Stdio::null());
    cmd.stderr(Stdio::null());

    #[cfg(target_os = "windows")]
    {
        use std::os::windows::process::CommandExt;
        cmd.creation_flags(0x08000000);
    }

    cmd
}

// ── Port-based kill helpers (Windows / macOS) ────────────────────────────────

/// Return all PIDs that have a TCP LISTEN socket on `port`.
/// Uses platform-specific tooling; sync parse, async-friendly command.
#[cfg(not(target_os = "linux"))]
async fn pids_on_port(port: u16) -> Vec<u32> {
    #[cfg(target_os = "windows")]
    {
        // PowerShell Get-NetTCPConnection  →  locale-independent, one PID per line
        let mut cmd = tokio::process::Command::new("powershell.exe");
        cmd.args([
            "-NoProfile",
            "-Command",
            &format!(
                "(Get-NetTCPConnection -LocalPort {port} -State Listen \
                 -ErrorAction SilentlyContinue).OwningProcess"
            ),
        ]);
        {
            // CREATE_NO_WINDOW — prevents the console flash when polled every 2 s
            use std::os::windows::process::CommandExt;
            cmd.creation_flags(0x08000000);
        }
        let out = match cmd.output().await {
            Ok(o) => o,
            Err(e) => {
                eprintln!("[pids_on_port] PowerShell Get-NetTCPConnection error: {e}");
                return vec![];
            }
        };
        let text = String::from_utf8_lossy(&out.stdout);
        let mut pids: Vec<u32> = Vec::new();
        for line in text.lines() {
            if let Ok(pid) = line.trim().parse::<u32>() {
                if !pids.contains(&pid) {
                    pids.push(pid);
                }
            }
        }
        pids
    }
    #[cfg(target_os = "macos")]
    {
        // lsof -nP -iTCP:<port> -sTCP:LISTEN -t  →  one PID per line
        let out = match tokio::process::Command::new("lsof")
            .args([
                "-nP",
                &format!("-iTCP:{port}"),
                "-sTCP:LISTEN",
                "-t",
            ])
            .output()
            .await
        {
            Ok(o) => o,
            Err(e) => {
                eprintln!("[pids_on_port] lsof error: {e}");
                return vec![];
            }
        };
        String::from_utf8_lossy(&out.stdout)
            .lines()
            .filter_map(|l| l.trim().parse::<u32>().ok())
            .collect()
    }
}

/// Kill **all** processes whose command line matches `pattern`.
///
/// On Windows uses `Get-CimInstance Win32_Process` to find PIDs by command line,
/// then `taskkill /F /T` (with `/T` to kill the entire process tree).
/// On macOS uses `pgrep -f`.
/// Returns the number of processes killed.
#[cfg(not(target_os = "linux"))]
async fn kill_by_cmdline(pattern: &str, label: &str) -> u32 {
    let mut killed = 0u32;

    #[cfg(target_os = "windows")]
    {
        // Get-CimInstance is fast and gives us CommandLine + ProcessId.
        let ps_cmd = format!(
            "(Get-CimInstance Win32_Process | Where-Object {{ $_.CommandLine -like '*{}*' }}).ProcessId",
            pattern
        );
        let mut cmd = tokio::process::Command::new("powershell.exe");
        cmd.args(["-NoProfile", "-Command", &ps_cmd]);
        {
            // CREATE_NO_WINDOW — no console flash during stop operations
            use std::os::windows::process::CommandExt;
            cmd.creation_flags(0x08000000);
        }
        let out = match cmd.output().await {
            Ok(o) => o,
            Err(e) => {
                eprintln!("[kill_by_cmdline] PowerShell error for {label}: {e}");
                return 0;
            }
        };
        let text = String::from_utf8_lossy(&out.stdout);
        let pids: Vec<u32> = text
            .lines()
            .filter_map(|l| l.trim().parse::<u32>().ok())
            .collect();

        for pid in pids {
            // /T = kill entire process tree (catches child workers)
            let mut kill_cmd = tokio::process::Command::new("taskkill.exe");
            kill_cmd.args(["/F", "/T", "/PID", &pid.to_string()]);
            {
                use std::os::windows::process::CommandExt;
                kill_cmd.creation_flags(0x08000000);
            }
            let result = kill_cmd.output().await;
            match result {
                Ok(o) if o.status.success() => {
                    eprintln!("[kill_by_cmdline] killed {label} pid {pid}");
                    killed += 1;
                }
                Ok(o) => {
                    eprintln!(
                        "[kill_by_cmdline] kill {label} pid {pid} failed: {}",
                        String::from_utf8_lossy(&o.stderr).trim()
                    );
                }
                Err(e) => {
                    eprintln!("[kill_by_cmdline] kill {label} pid {pid} error: {e}");
                }
            }
        }
    }

    #[cfg(target_os = "macos")]
    {
        let out = match tokio::process::Command::new("pgrep")
            .args(["-f", pattern])
            .output()
            .await
        {
            Ok(o) => o,
            Err(e) => {
                eprintln!("[kill_by_cmdline] pgrep error for {label}: {e}");
                return 0;
            }
        };
        let pids: Vec<u32> = String::from_utf8_lossy(&out.stdout)
            .lines()
            .filter_map(|l| l.trim().parse::<u32>().ok())
            .collect();

        for pid in pids {
            let result = tokio::process::Command::new("kill")
                .args(["-9", &pid.to_string()])
                .output()
                .await;
            if matches!(result, Ok(o) if o.status.success()) {
                eprintln!("[kill_by_cmdline] killed {label} pid {pid}");
                killed += 1;
            }
        }
    }

    if killed > 0 {
        tokio::time::sleep(Duration::from_millis(300)).await;
    }
    killed
}

/// Kill any process currently listening on `port`.
/// Returns `Ok(())` if at least one kill succeeded, `Err(...)` otherwise.
#[cfg(not(target_os = "linux"))]
async fn kill_on_port(port: u16, service: &'static str) -> Result<(), String> {
    let pids = pids_on_port(port).await;
    if pids.is_empty() {
        return Err(format!("no process listening on port {port}"));
    }

    let mut any_ok = false;

    for pid in pids {
        #[cfg(target_os = "windows")]
        let result = {
            let mut kill_cmd = tokio::process::Command::new("taskkill.exe");
            kill_cmd.args(["/F", "/PID", &pid.to_string()]);
            {
                use std::os::windows::process::CommandExt;
                kill_cmd.creation_flags(0x08000000);
            }
            kill_cmd.output().await
        };

        #[cfg(target_os = "macos")]
        let result = tokio::process::Command::new("kill")
            .args(["-9", &pid.to_string()])
            .output()
            .await;

        match result {
            Ok(o) if o.status.success() => {
                eprintln!("[kill_on_port] killed {service} pid {pid} on port {port}");
                any_ok = true;
            }
            Ok(o) => {
                eprintln!(
                    "[kill_on_port] kill pid {pid} failed: {}",
                    String::from_utf8_lossy(&o.stderr).trim()
                );
            }
            Err(e) => {
                eprintln!("[kill_on_port] kill pid {pid} error: {e}");
            }
        }
    }

    if any_ok {
        tokio::time::sleep(Duration::from_millis(300)).await;
        Ok(())
    } else {
        Err(format!("all kill attempts for {service} on port {port} failed"))
    }
}

// ── Service management — Linux (systemctl) ────────────────────────────────────

#[cfg(target_os = "linux")]
async fn run_systemctl(args: &[&str]) -> Result<String, String> {
    let output = tokio::process::Command::new("systemctl")
        .args(args)
        .output()
        .await
        .map_err(|e| format!("failed to run systemctl: {e}"))?;

    if output.status.success() {
        Ok(String::from_utf8_lossy(&output.stdout).trim().to_string())
    } else {
        let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
        let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
        Err(if !stderr.is_empty() { stderr } else { stdout })
    }
}

#[cfg(target_os = "linux")]
async fn systemctl_is_active(unit: &str) -> String {
    let output = tokio::process::Command::new("systemctl")
        .args(["--user", "is-active", unit])
        .output()
        .await;
    match output {
        Ok(o) => String::from_utf8_lossy(&o.stdout).trim().to_string(),
        Err(_) => "error".into(),
    }
}

// ── OpenClaw CLI + token helpers ──────────────────────────────────────────────

/// Extract the token value from a `#token=<TOKEN>` fragment in CLI output.
fn extract_hash_token(text: &str) -> Option<String> {
    text.find("#token=")
        .map(|pos| &text[pos + "#token=".len()..])
        .and_then(|after| {
            let end = after
                .find(|c: char| c.is_ascii_whitespace())
                .unwrap_or(after.len());
            let tok = &after[..end];
            if tok.is_empty() { None } else { Some(tok.to_string()) }
        })
}

/// Resolve the argv prefix for spawning the OpenClaw CLI on this machine.
///
/// On Windows, npm global installs create a `.cmd` shim; we resolve through
/// to the underlying `node openclaw.mjs` so we can pass env vars cleanly.
fn _resolve_openclaw_cli_argv() -> Option<Vec<String>> {
    #[cfg(target_os = "windows")]
    {
        // Try the known nvm/npm global paths first, then fall back to PATH.
        let candidates: Vec<PathBuf> = {
            let mut v = Vec::new();
            // nvm-windows style: %APPDATA%\nvm\<version>\node_modules\openclaw
            if let Ok(appdata) = std::env::var("APPDATA") {
                let nvm_dir = PathBuf::from(&appdata).join("nvm");
                if let Ok(entries) = std::fs::read_dir(&nvm_dir) {
                    for entry in entries.flatten() {
                        let script = entry.path()
                            .join("node_modules")
                            .join("openclaw")
                            .join("openclaw.mjs");
                        if script.exists() {
                            v.push(script);
                        }
                    }
                }
            }
            // npm global: %ProgramFiles%\nodejs\node_modules\openclaw
            let pf = PathBuf::from(
                std::env::var("ProgramFiles").unwrap_or_else(|_| r"C:\Program Files".into()),
            );
            let npm_script = pf
                .join("nodejs")
                .join("node_modules")
                .join("openclaw")
                .join("openclaw.mjs");
            if npm_script.exists() {
                v.push(npm_script);
            }
            v
        };

        if let Some(script) = candidates.first() {
            // Find node binary
            let node_paths = ["node.exe"];
            for name in &node_paths {
                if let Ok(path_var) = std::env::var("PATH") {
                    for dir in std::env::split_paths(&path_var) {
                        let candidate = dir.join(name);
                        if candidate.exists() {
                            return Some(vec![
                                candidate.to_string_lossy().to_string(),
                                script.to_string_lossy().to_string(),
                            ]);
                        }
                    }
                }
            }
        }
        None
    }
    #[cfg(not(target_os = "windows"))]
    {
        // On Unix, just use "openclaw" from PATH.
        if let Ok(path_var) = std::env::var("PATH") {
            for dir in std::env::split_paths(&path_var) {
                let candidate = dir.join("openclaw");
                if candidate.exists() {
                    return Some(vec![candidate.to_string_lossy().to_string()]);
                }
            }
        }
        None
    }
}

// ── Tauri commands ────────────────────────────────────────────────────────────

pub mod commands {
    use super::*;

    // ── JARVIS backend ────────────────────────────────────────────────────────

    #[tauri::command]
    pub async fn start_jarvis() -> Result<String, String> {
        #[cfg(target_os = "linux")]
        {
            run_systemctl(&["--user", "start", "jarvis-backend.service"]).await
        }
        #[cfg(not(target_os = "linux"))]
        {
            let repo = repo_root()?;
            let state = child_state("backend").await;
            if state == ChildState::Running {
                return Ok("already running".into());
            }
            let child = build_backend_command(&repo)
                .spawn()
                .map_err(|e| format!("failed to spawn backend: {e}"))?;
            CHILDREN.lock().await.insert("backend", child);
            Ok("started".into())
        }
    }

    #[tauri::command]
    pub async fn stop_jarvis() -> Result<String, String> {
        #[cfg(target_os = "linux")]
        {
            run_systemctl(&["--user", "stop", "jarvis-backend.service"]).await
        }
        #[cfg(not(target_os = "linux"))]
        {
            // 1. Kill tracked child (if any)
            {
                let mut map = CHILDREN.lock().await;
                if let Some(mut child) = map.remove("backend") {
                    let _ = child.kill().await;
                    let _ = child.wait().await;
                }
            }

            // 2. Kill anything still listening on port 8766
            let _ = kill_on_port(8766, "backend").await;

            // 3. Kill orphaned python processes running "-m main" (zombie cleanup)
            let repo = repo_root().unwrap_or_default();
            let venv_python = repo.join(".venv").to_string_lossy().to_string();
            // Match on the venv path so we only kill JARVIS pythons, not random ones
            let pattern = if venv_python.is_empty() {
                "python*-m main".to_string()
            } else {
                // Escape backslashes for the PowerShell -like pattern
                format!("{}*-m main", venv_python.replace('\\', "\\\\"))
            };
            let orphans = kill_by_cmdline(&pattern, "backend-orphan").await;

            if orphans > 0 {
                Ok(format!("stopped (cleaned {orphans} orphan(s))"))
            } else {
                Ok("stopped".into())
            }
        }
    }

    #[tauri::command]
    pub async fn restart_jarvis() -> Result<String, String> {
        #[cfg(target_os = "linux")]
        {
            run_systemctl(&["--user", "restart", "jarvis-backend.service"]).await
        }
        #[cfg(not(target_os = "linux"))]
        {
            drop(stop_jarvis().await);
            start_jarvis().await
        }
    }

    #[tauri::command]
    pub async fn jarvis_status() -> Result<StatusInfo, String> {
        #[cfg(target_os = "linux")]
        {
            let state = systemctl_is_active("jarvis-backend.service").await;
            let http_ok = check_http_jarvis().await;
            Ok(StatusInfo { state, http_ok })
        }
        #[cfg(not(target_os = "linux"))]
        {
            let http_ok = check_http_jarvis().await;
            let state = if http_ok {
                "active".into()
            } else {
                match child_state("backend").await {
                    ChildState::Running => "active".into(),
                    ChildState::Failed => "failed".into(),
                    _ => "inactive".into(),
                }
            };
            Ok(StatusInfo { state, http_ok })
        }
    }

    // ── JARVIS frontend ───────────────────────────────────────────────────────

    #[tauri::command]
    pub async fn start_frontend() -> Result<String, String> {
        #[cfg(target_os = "linux")]
        {
            run_systemctl(&["--user", "start", "jarvis-frontend.service"]).await
        }
        #[cfg(not(target_os = "linux"))]
        {
            let repo = repo_root()?;
            let state = child_state("frontend").await;
            if state == ChildState::Running {
                return Ok("already running".into());
            }
            let child = build_frontend_command(&repo)
                .spawn()
                .map_err(|e| format!("failed to spawn frontend: {e}"))?;
            CHILDREN.lock().await.insert("frontend", child);
            Ok("started".into())
        }
    }

    #[tauri::command]
    pub async fn stop_frontend() -> Result<String, String> {
        #[cfg(target_os = "linux")]
        {
            run_systemctl(&["--user", "stop", "jarvis-frontend.service"]).await
        }
        #[cfg(not(target_os = "linux"))]
        {
            // 1. Kill tracked child (if any)
            {
                let mut map = CHILDREN.lock().await;
                if let Some(mut child) = map.remove("frontend") {
                    let _ = child.kill().await;
                    let _ = child.wait().await;
                }
            }

            // 2. Kill anything still listening on port 5173
            let _ = kill_on_port(5173, "frontend").await;

            // 3. Kill orphaned node processes running "vite" in the frontend dir
            let repo = repo_root().unwrap_or_default();
            let frontend_dir = repo.join("frontend").to_string_lossy().to_string();
            if !frontend_dir.is_empty() {
                let pattern = format!("{}*vite", frontend_dir.replace('\\', "\\\\"));
                kill_by_cmdline(&pattern, "frontend-orphan").await;
            }

            Ok("stopped".into())
        }
    }

    #[tauri::command]
    pub async fn restart_frontend() -> Result<String, String> {
        #[cfg(target_os = "linux")]
        {
            run_systemctl(&["--user", "restart", "jarvis-frontend.service"]).await
        }
        #[cfg(not(target_os = "linux"))]
        {
            drop(stop_frontend().await);
            start_frontend().await
        }
    }

    #[tauri::command]
    pub async fn frontend_status() -> Result<StatusInfo, String> {
        #[cfg(target_os = "linux")]
        {
            let state = systemctl_is_active("jarvis-frontend.service").await;
            let http_ok = check_http_frontend().await;
            Ok(StatusInfo { state, http_ok })
        }
        #[cfg(not(target_os = "linux"))]
        {
            let http_ok = check_http_frontend().await;
            let state = if http_ok {
                "active".into()
            } else {
                match child_state("frontend").await {
                    ChildState::Running => "active".into(),
                    ChildState::Failed => "failed".into(),
                    _ => "inactive".into(),
                }
            };
            Ok(StatusInfo { state, http_ok })
        }
    }

    // ── OpenClaw (remote probe only) ──────────────────────────────────────────

    #[tauri::command]
    pub async fn start_openclaw() -> Result<String, String> {
        Err("OpenClaw is remote; manage it on its host".into())
    }

    #[tauri::command]
    pub async fn stop_openclaw() -> Result<String, String> {
        Err("OpenClaw is remote; manage it on its host".into())
    }

    #[tauri::command]
    pub async fn restart_openclaw() -> Result<String, String> {
        Err("OpenClaw is remote; manage it on its host".into())
    }

    #[tauri::command]
    pub async fn openclaw_status() -> Result<StatusInfo, String> {
        let http_ok = check_http_openclaw().await;
        let state = if http_ok { "remote" } else { "unreachable" }.to_string();
        Ok(StatusInfo { state, http_ok })
    }

    /// Return the OpenClaw URL with an auth token appended as a URL hash fragment.
    ///
    /// Tries multiple strategies in order:
    /// 1. Local CLI → `openclaw dashboard --no-open` → parse `#token=`
    /// 2. Local config file `~/.openclaw/openclaw.json` → `gateway.auth.token`
    /// 3. Fallback → bare URL
    ///
    /// Any failure logs a warning and falls through to the next strategy.
    #[tauri::command]
    pub async fn openclaw_url() -> Result<String, String> {
        let dashboard_base = openclaw_base_url();
        let fallback = format!("{}/", dashboard_base.trim_end_matches('/'));

        // ── Strategy 1: local CLI `openclaw dashboard --no-open` ─────────────
        {
            let cli_argv = _resolve_openclaw_cli_argv();
            if let Some(argv) = cli_argv {
                let mut cmd = tokio::process::Command::new(&argv[0]);
                for arg in &argv[1..] {
                    cmd.arg(arg);
                }
                cmd.args(["dashboard", "--no-open"]);
                // Allow insecure private WS for LAN gateways.
                cmd.env("OPENCLAW_ALLOW_INSECURE_PRIVATE_WS", "1");

                match tokio::time::timeout(Duration::from_secs(10), cmd.output()).await {
                    Ok(Ok(output)) if output.status.success() => {
                        let stdout = String::from_utf8_lossy(&output.stdout);
                        if let Some(token) = extract_hash_token(&stdout) {
                            return Ok(format!(
                                "{}/#token={}",
                                dashboard_base.trim_end_matches('/'),
                                token
                            ));
                        }
                        eprintln!(
                            "[openclaw_url] local CLI ok but #token= not found"
                        );
                    }
                    Ok(Ok(output)) => {
                        let stderr = String::from_utf8_lossy(&output.stderr);
                        eprintln!(
                            "[openclaw_url] local CLI exited {:?}: {}",
                            output.status.code(),
                            stderr.chars().take(200).collect::<String>()
                        );
                    }
                    Ok(Err(e)) => {
                        eprintln!("[openclaw_url] local CLI spawn error: {}", e);
                    }
                    Err(_) => {
                        eprintln!("[openclaw_url] local CLI timed out");
                    }
                }
            }
        }

        // ── Strategy 2: read ~/.openclaw/openclaw.json ───────────────────────
        let home = {
            #[cfg(target_os = "windows")]
            { std::env::var("USERPROFILE").unwrap_or_else(|_| "C:\\Users\\user".into()) }
            #[cfg(not(target_os = "windows"))]
            { std::env::var("HOME").unwrap_or_else(|_| "/root".into()) }
        };
        let path = format!("{}/.openclaw/openclaw.json", home);

        if let Ok(contents) = tokio::fs::read_to_string(&path).await {
            if let Ok(json) = serde_json::from_str::<serde_json::Value>(&contents) {
                let token = json
                    .get("gateway")
                    .and_then(|g| g.get("auth"))
                    .and_then(|a| a.get("token"))
                    .and_then(|t| t.as_str());

                if let Some(t) = token {
                    if !t.is_empty() {
                        return Ok(format!("{}?token={}", fallback, t));
                    }
                }
            }
        }

        // ── Strategy 3: bare URL fallback ────────────────────────────────────
        eprintln!(
            "[openclaw_url] WARNING: no token found via any strategy — returning bare URL"
        );
        Ok(fallback)
    }

    // ── OpenClaw target toggle ────────────────────────────────────────────────

    /// Return the currently persisted OpenClaw settings and the resolved URL.
    #[tauri::command]
    pub async fn get_openclaw_target() -> Result<OpenclawTargetInfo, String> {
        let s = read_openclaw_settings();
        Ok(to_info(&s))
    }

    /// Validate and persist a new OpenClaw target, then return the updated info.
    ///
    /// `target` must be `"local"` or `"remote"`; any other value returns `Err`.
    #[tauri::command]
    pub async fn set_openclaw_target(target: String) -> Result<OpenclawTargetInfo, String> {
        match target.as_str() {
            "local" | "remote" => {}
            other => {
                return Err(format!(
                    "invalid openclaw target {:?}: must be \"local\" or \"remote\"",
                    other
                ))
            }
        }
        let mut s = read_openclaw_settings();
        s.target = target;
        write_openclaw_settings(&s)?;
        Ok(to_info(&s))
    }

    /// Persist a new remote URL for the OpenClaw gateway (Tailscale or LAN URL).
    ///
    /// Example: `http://100.84.x.y:18789` for a Tailscale-reachable gateway.
    #[tauri::command]
    pub async fn set_openclaw_remote_url(remote_url: String) -> Result<OpenclawTargetInfo, String> {
        let trimmed = remote_url.trim();
        if trimmed.is_empty() {
            return Err("remote_url must not be empty".into());
        }
        if !trimmed.starts_with("http://") && !trimmed.starts_with("https://") {
            return Err("remote_url must start with http:// or https://".into());
        }
        let mut s = read_openclaw_settings();
        s.remote_url = trimmed.into();
        write_openclaw_settings(&s)?;
        Ok(to_info(&s))
    }

    // ── Generic HTTP check (kept for potential future use) ────────────────────

    #[tauri::command]
    pub async fn check_http(url: String) -> bool {
        check_http_url(&url).await
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![
            commands::start_jarvis,
            commands::stop_jarvis,
            commands::restart_jarvis,
            commands::jarvis_status,
            commands::start_openclaw,
            commands::stop_openclaw,
            commands::restart_openclaw,
            commands::openclaw_status,
            commands::openclaw_url,
            commands::get_openclaw_target,
            commands::set_openclaw_target,
            commands::set_openclaw_remote_url,
            commands::start_frontend,
            commands::stop_frontend,
            commands::restart_frontend,
            commands::frontend_status,
            commands::check_http,
        ])
        .run(tauri::generate_context!())
        .expect("error while running JARVIS Controller");
}
