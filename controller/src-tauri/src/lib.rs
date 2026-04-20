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
}

/// Response type exposed to the frontend via Tauri commands.
#[derive(Debug, Serialize)]
pub struct OpenclawTargetInfo {
    /// `"local"` or `"remote"`.
    pub target: String,
    /// The resolved base URL for that target.
    pub url: String,
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

/// Read the persisted OpenClaw target.
/// Returns `"remote"` whenever the file is missing or contains invalid JSON.
fn read_openclaw_target() -> String {
    let path = settings_path();
    let contents = match std::fs::read_to_string(&path) {
        Ok(c) => c,
        Err(_) => return "remote".into(),
    };
    let settings: OpenclawSettings = match serde_json::from_str(&contents) {
        Ok(s) => s,
        Err(_) => return "remote".into(),
    };
    match settings.openclaw.target.as_str() {
        "local" | "remote" => settings.openclaw.target,
        _ => "remote".into(),
    }
}

/// Persist the OpenClaw target.
/// Creates the config directory if it does not yet exist.
fn write_openclaw_target(target: &str) -> Result<(), String> {
    let path = settings_path();
    if let Some(dir) = path.parent() {
        std::fs::create_dir_all(dir)
            .map_err(|e| format!("cannot create settings dir: {e}"))?;
    }
    let settings = OpenclawSettings {
        openclaw: OpenclawSection {
            target: target.to_string(),
        },
    };
    let json = serde_json::to_string_pretty(&settings)
        .map_err(|e| format!("cannot serialise settings: {e}"))?;
    std::fs::write(&path, json).map_err(|e| format!("cannot write settings: {e}"))
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
///    `"remote"` → `http://192.168.1.118:18789`.
/// 3. Hardcoded fallback `http://127.0.0.1:18789`.
fn openclaw_base_url() -> String {
    if let Ok(v) = std::env::var("JARVIS_OPENCLAW_URL") {
        if !v.trim().is_empty() {
            return v;
        }
    }
    match read_openclaw_target().as_str() {
        "local" => "http://127.0.0.1:18789".into(),
        "remote" => "http://192.168.1.118:18789".into(),
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
                if status.success() {
                    ChildState::Exited
                } else {
                    ChildState::Failed
                }
            }
            Err(_) => ChildState::Failed,
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

// ── SSH tunnel (Windows / macOS only) ────────────────────────────────────────

#[cfg(not(target_os = "linux"))]
const SSH_TUNNEL_ARGS: &[&str] = &[
    "-o", "BatchMode=yes",
    "-o", "ServerAliveInterval=30",
    "-o", "ExitOnForwardFailure=yes",
    "-N",
    "-L", "18789:localhost:18789",
    "laptop",
];

/// Ensure the SSH tunnel to the remote OpenClaw gateway is up.
///
/// - If the OpenClaw target is `"local"`, returns `Ok(())` immediately.
/// - If port 18789 already has a listener, assumes the tunnel is up.
/// - Otherwise spawns `ssh <SSH_TUNNEL_ARGS>` and polls for up to 5 s.
#[cfg(not(target_os = "linux"))]
async fn ensure_ssh_tunnel() -> Result<(), String> {
    use std::process::Stdio;

    if read_openclaw_target() == "local" {
        return Ok(());
    }

    if !pids_on_port(18789).await.is_empty() {
        return Ok(());
    }

    let mut cmd = tokio::process::Command::new("ssh");
    cmd.args(SSH_TUNNEL_ARGS);
    cmd.stdin(Stdio::null());
    cmd.stdout(Stdio::null());
    cmd.stderr(Stdio::null());

    #[cfg(target_os = "windows")]
    {
        use std::os::windows::process::CommandExt;
        cmd.creation_flags(0x08000000);
    }

    let child = cmd
        .spawn()
        .map_err(|e| format!("failed to spawn SSH tunnel: {e}"))?;

    CHILDREN.lock().await.insert("ssh_tunnel", child);

    // Poll up to 5 s (25 × 200 ms) for port 18789 to become live.
    for _ in 0..25 {
        tokio::time::sleep(Duration::from_millis(200)).await;
        if !pids_on_port(18789).await.is_empty() {
            return Ok(());
        }
    }

    // Timed out — kill the child and report failure.
    let mut map = CHILDREN.lock().await;
    if let Some(mut child) = map.remove("ssh_tunnel") {
        let _ = child.kill().await;
        let _ = child.wait().await;
    }
    Err("SSH tunnel did not come up within 5s".into())
}

/// Tear down the tracked SSH tunnel child, if any.
#[cfg(not(target_os = "linux"))]
async fn stop_ssh_tunnel() -> Result<(), String> {
    let mut map = CHILDREN.lock().await;
    if let Some(mut child) = map.remove("ssh_tunnel") {
        let _ = child.kill().await;
        let _ = child.wait().await;
    }
    Ok(())
}

// ── Port-based kill helpers (Windows / macOS) ────────────────────────────────

/// Return all PIDs that have a TCP LISTEN socket on `port`.
/// Uses platform-specific tooling; sync parse, async-friendly command.
#[cfg(not(target_os = "linux"))]
async fn pids_on_port(port: u16) -> Vec<u32> {
    #[cfg(target_os = "windows")]
    {
        // PowerShell Get-NetTCPConnection  →  locale-independent, one PID per line
        let out = match tokio::process::Command::new("powershell.exe")
            .args([
                "-NoProfile",
                "-Command",
                &format!(
                    "(Get-NetTCPConnection -LocalPort {port} -State Listen \
                     -ErrorAction SilentlyContinue).OwningProcess"
                ),
            ])
            .output()
            .await
        {
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
        let result = tokio::process::Command::new("taskkill.exe")
            .args(["/F", "/PID", &pid.to_string()])
            .output()
            .await;

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
            ensure_ssh_tunnel().await?;
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
            let result = {
                let mut map = CHILDREN.lock().await;
                if let Some(mut child) = map.remove("backend") {
                    child.kill().await.map_err(|e| format!("kill failed: {e}"))?;
                    let _ = child.wait().await;
                    Ok("stopped".into())
                } else {
                    drop(map);
                    match kill_on_port(8766, "backend").await {
                        Ok(()) => Ok("stopped (via port fallback)".into()),
                        Err(_) => Ok("not running".into()),
                    }
                }
            };
            let _ = stop_ssh_tunnel().await;
            result
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
            let state = match child_state("backend").await {
                ChildState::Running => "active".into(),
                ChildState::Failed => "failed".into(),
                _ if http_ok => "active".into(),
                _ => "inactive".into(),
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
            let mut map = CHILDREN.lock().await;
            if let Some(mut child) = map.remove("frontend") {
                child.kill().await.map_err(|e| format!("kill failed: {e}"))?;
                let _ = child.wait().await;
                Ok("stopped".into())
            } else {
                drop(map);
                match kill_on_port(5173, "frontend").await {
                    Ok(()) => Ok("stopped (via port fallback)".into()),
                    Err(_) => Ok("not running".into()),
                }
            }
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
            let state = match child_state("frontend").await {
                ChildState::Running => "active".into(),
                ChildState::Failed => "failed".into(),
                _ if http_ok => "active".into(),
                _ => "inactive".into(),
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
    /// If `JARVIS_OPENCLAW_SSH_HOST` is set → SSH to that host, run
    /// `openclaw dashboard`, parse the `#token=<TOKEN>` fragment from its output,
    /// and return `<base>/#token=<TOKEN>`.
    ///
    /// Otherwise → read token from `~/.openclaw/openclaw.json` (local-file path,
    /// Linux only) and return `<base>?token=<TOKEN>`.
    ///
    /// Any failure (SSH timeout, no token in output, missing file, parse error)
    /// logs a warning and falls back to the bare base URL.
    #[tauri::command]
    pub async fn openclaw_url() -> Result<String, String> {
        let base = openclaw_base_url();
        let fallback = format!("{}/", base.trim_end_matches('/'));

        // ── Remote path: SSH to JARVIS_OPENCLAW_SSH_HOST ─────────────────────
        if let Ok(ssh_host) = std::env::var("JARVIS_OPENCLAW_SSH_HOST") {
            if !ssh_host.trim().is_empty() {
                let remote_cmd = concat!(
                    r#"export NVM_DIR="$HOME/.nvm" && "#,
                    r#". "$NVM_DIR/nvm.sh" && "#,
                    r#"openclaw dashboard 2>&1"#
                );

                let ssh_future = tokio::process::Command::new("ssh")
                    .args([
                        "-o", "BatchMode=yes",
                        "-o", "ConnectTimeout=5",
                        ssh_host.trim(),
                        remote_cmd,
                    ])
                    .output();

                let output = match tokio::time::timeout(
                    Duration::from_secs(10),
                    ssh_future,
                )
                .await
                {
                    Ok(Ok(o)) => o,
                    Ok(Err(e)) => {
                        eprintln!("[openclaw_url] WARNING: ssh spawn error: {}", e);
                        return Ok(fallback);
                    }
                    Err(_) => {
                        eprintln!("[openclaw_url] WARNING: ssh timed out after 10 s");
                        return Ok(fallback);
                    }
                };

                if !output.status.success() {
                    eprintln!(
                        "[openclaw_url] WARNING: ssh exited with {:?}",
                        output.status.code()
                    );
                    return Ok(fallback);
                }

                let stdout = String::from_utf8_lossy(&output.stdout);

                // Find "#token=" and take everything up to the next whitespace / EOL.
                // The CLI prints a line like:
                //   Dashboard URL: http://127.0.0.1:18789/#token=<TOKEN>
                let token: Option<&str> = stdout
                    .find("#token=")
                    .map(|pos| &stdout[pos + "#token=".len()..])
                    .and_then(|after| {
                        let end = after
                            .find(|c: char| c.is_ascii_whitespace())
                            .unwrap_or(after.len());
                        let tok = &after[..end];
                        if tok.is_empty() { None } else { Some(tok) }
                    });

                return match token {
                    Some(t) => {
                        Ok(format!("{}/#token={}", base.trim_end_matches('/'), t))
                    }
                    None => {
                        eprintln!(
                            "[openclaw_url] WARNING: #token= not found in ssh output"
                        );
                        Ok(fallback)
                    }
                };
            }
        }

        // ── Local path: read ~/.openclaw/openclaw.json ────────────────────────
        let home = {
            #[cfg(target_os = "windows")]
            { std::env::var("USERPROFILE").unwrap_or_else(|_| "C:\\Users\\user".into()) }
            #[cfg(not(target_os = "windows"))]
            { std::env::var("HOME").unwrap_or_else(|_| "/root".into()) }
        };
        let path = format!("{}/.openclaw/openclaw.json", home);

        let contents = match tokio::fs::read_to_string(&path).await {
            Ok(c) => c,
            Err(e) => {
                eprintln!("[openclaw_url] WARNING: could not read {}: {}", path, e);
                return Ok(fallback);
            }
        };

        let json: serde_json::Value = match serde_json::from_str(&contents) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("[openclaw_url] WARNING: failed to parse {}: {}", path, e);
                return Ok(fallback);
            }
        };

        let token = json
            .get("gateway")
            .and_then(|g| g.get("auth"))
            .and_then(|a| a.get("token"))
            .and_then(|t| t.as_str());

        match token {
            Some(t) if !t.is_empty() => Ok(format!("{}?token={}", fallback, t)),
            _ => {
                eprintln!(
                    "[openclaw_url] WARNING: gateway.auth.token not found or empty in {}",
                    path
                );
                Ok(fallback)
            }
        }
    }

    // ── OpenClaw target toggle ────────────────────────────────────────────────

    /// Return the currently persisted OpenClaw target and its resolved URL.
    #[tauri::command]
    pub async fn get_openclaw_target() -> Result<OpenclawTargetInfo, String> {
        let target = read_openclaw_target();
        let url = openclaw_base_url();
        Ok(OpenclawTargetInfo { target, url })
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
        write_openclaw_target(&target)?;
        let url = match target.as_str() {
            "local" => "http://127.0.0.1:18789".into(),
            _ => "http://192.168.1.118:18789".into(),
        };
        Ok(OpenclawTargetInfo { target, url })
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
            commands::start_frontend,
            commands::stop_frontend,
            commands::restart_frontend,
            commands::frontend_status,
            commands::check_http,
        ])
        .run(tauri::generate_context!())
        .expect("error while running JARVIS Controller");
}
