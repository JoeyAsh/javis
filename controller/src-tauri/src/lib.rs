use serde::{Deserialize, Serialize};
use std::time::Duration;
use tokio::process::Command;

#[derive(Debug, Serialize, Deserialize)]
pub struct StatusInfo {
    pub state: String,
    pub http_ok: bool,
}

/// Run a systemctl --user command and return trimmed stdout.
/// For start/stop we treat non-zero exit as an error.
async fn run_systemctl(args: &[&str]) -> Result<String, String> {
    let output = Command::new("systemctl")
        .args(args)
        .output()
        .await
        .map_err(|e| format!("failed to run systemctl: {e}"))?;

    if output.status.success() {
        Ok(String::from_utf8_lossy(&output.stdout).trim().to_string())
    } else {
        let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
        let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
        let msg = if !stderr.is_empty() { stderr } else { stdout };
        Err(msg)
    }
}

/// Check HTTP health endpoint for JARVIS; returns true on any 2xx within 500ms.
async fn check_http_jarvis() -> bool {
    check_http_url("http://127.0.0.1:8766/health").await
}

/// Check HTTP health endpoint for OpenClaw; returns true on any 2xx within 500ms.
async fn check_http_openclaw() -> bool {
    check_http_url("http://127.0.0.1:18789/").await
}

/// Check HTTP reachability of the Vite dev server; returns true on any 2xx within 500ms.
async fn check_http_frontend() -> bool {
    check_http_url("http://127.0.0.1:5173/").await
}

/// Generic HTTP check: true if URL responds with 2xx within 500 ms.
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

pub mod commands {
    use super::{StatusInfo, check_http_frontend, check_http_jarvis, check_http_openclaw, run_systemctl};
    use tokio::process::Command;

    // ── JARVIS commands ──────────────────────────────────────────────────────

    #[tauri::command]
    pub async fn start_jarvis() -> Result<String, String> {
        run_systemctl(&["--user", "start", "jarvis-backend.service"]).await
    }

    #[tauri::command]
    pub async fn stop_jarvis() -> Result<String, String> {
        run_systemctl(&["--user", "stop", "jarvis-backend.service"]).await
    }

    #[tauri::command]
    pub async fn restart_jarvis() -> Result<String, String> {
        run_systemctl(&["--user", "restart", "jarvis-backend.service"]).await
    }

    #[tauri::command]
    pub async fn jarvis_status() -> Result<StatusInfo, String> {
        // is-active exits non-zero when not active; that's expected — capture stdout regardless.
        let output = Command::new("systemctl")
            .args(["--user", "is-active", "jarvis-backend.service"])
            .output()
            .await
            .map_err(|e| format!("failed to run systemctl: {e}"))?;

        let state = String::from_utf8_lossy(&output.stdout).trim().to_string();
        let http_ok = check_http_jarvis().await;

        Ok(StatusInfo { state, http_ok })
    }

    // ── OpenClaw commands ────────────────────────────────────────────────────

    #[tauri::command]
    pub async fn start_openclaw() -> Result<String, String> {
        run_systemctl(&["--user", "start", "openclaw-gateway.service"]).await
    }

    #[tauri::command]
    pub async fn stop_openclaw() -> Result<String, String> {
        run_systemctl(&["--user", "stop", "openclaw-gateway.service"]).await
    }

    #[tauri::command]
    pub async fn restart_openclaw() -> Result<String, String> {
        run_systemctl(&["--user", "restart", "openclaw-gateway.service"]).await
    }

    #[tauri::command]
    pub async fn openclaw_status() -> Result<StatusInfo, String> {
        let output = Command::new("systemctl")
            .args(["--user", "is-active", "openclaw-gateway.service"])
            .output()
            .await
            .map_err(|e| format!("failed to run systemctl: {e}"))?;

        let state = String::from_utf8_lossy(&output.stdout).trim().to_string();
        let http_ok = check_http_openclaw().await;

        Ok(StatusInfo { state, http_ok })
    }

    /// Read token from ~/.openclaw/openclaw.json (gateway.auth.token).
    /// Returns the full URL with ?token=… query param.
    /// Falls back to bare URL and logs a warning if file/token is missing.
    #[tauri::command]
    pub async fn openclaw_url() -> Result<String, String> {
        const BASE: &str = "http://127.0.0.1:18789/";

        let home = std::env::var("HOME").unwrap_or_else(|_| "/root".to_string());
        let path = format!("{}/.openclaw/openclaw.json", home);

        let contents = match tokio::fs::read_to_string(&path).await {
            Ok(c) => c,
            Err(e) => {
                eprintln!("[openclaw_url] WARNING: could not read {}: {}", path, e);
                return Ok(BASE.to_string());
            }
        };

        let json: serde_json::Value = match serde_json::from_str(&contents) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("[openclaw_url] WARNING: failed to parse {}: {}", path, e);
                return Ok(BASE.to_string());
            }
        };

        let token = json
            .get("gateway")
            .and_then(|g| g.get("auth"))
            .and_then(|a| a.get("token"))
            .and_then(|t| t.as_str());

        match token {
            Some(t) if !t.is_empty() => Ok(format!("{}?token={}", BASE, t)),
            _ => {
                eprintln!("[openclaw_url] WARNING: gateway.auth.token not found or empty in {}", path);
                Ok(BASE.to_string())
            }
        }
    }

    // ── Frontend commands ────────────────────────────────────────────────────

    #[tauri::command]
    pub async fn start_frontend() -> Result<String, String> {
        run_systemctl(&["--user", "start", "jarvis-frontend.service"]).await
    }

    #[tauri::command]
    pub async fn stop_frontend() -> Result<String, String> {
        run_systemctl(&["--user", "stop", "jarvis-frontend.service"]).await
    }

    #[tauri::command]
    pub async fn restart_frontend() -> Result<String, String> {
        run_systemctl(&["--user", "restart", "jarvis-frontend.service"]).await
    }

    #[tauri::command]
    pub async fn frontend_status() -> Result<StatusInfo, String> {
        let output = Command::new("systemctl")
            .args(["--user", "is-active", "jarvis-frontend.service"])
            .output()
            .await
            .map_err(|e| format!("failed to run systemctl: {e}"))?;

        let state = String::from_utf8_lossy(&output.stdout).trim().to_string();
        let http_ok = check_http_frontend().await;

        Ok(StatusInfo { state, http_ok })
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
            commands::start_frontend,
            commands::stop_frontend,
            commands::restart_frontend,
            commands::frontend_status,
        ])
        .run(tauri::generate_context!())
        .expect("error while running JARVIS Controller");
}
