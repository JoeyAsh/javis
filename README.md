# JARVIS

JARVIS (Just A Rather Very Intelligent System) is a voice-activated AI assistant that runs locally on your PC or Raspberry Pi. Say the wake word, speak your request — JARVIS transcribes it, reasons via Claude AI, and responds in a cloned voice. It can control your PC, manage smart home devices, search the web, and more.

## Requirements

- Python 3.12+, Node 20+
- Linux or macOS (Windows via WSL)
- Microphone and speakers
- Anthropic API key (direct or via OpenClaw gateway, port 18789)
- Home Assistant (optional, for smart home control)

## Quick Start

```bash
# Clone and set up Python environment
git clone https://github.com/yourusername/jarvis.git
cd jarvis
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure secrets
cp .env.example .env
# Edit .env — fill in at minimum ANTHROPIC_API_KEY

# Start backend (WebSocket :8765, HTTP :8766)
PYTHONPATH=src .venv/bin/python -m main

# In a separate terminal, start the frontend
cd frontend && npm install && npm run dev
# Open http://localhost:5173
```

## Setup — OpenClaw + Google Workspace (gog)

### Remote OpenClaw gateway

JARVIS routes Claude API calls through the OpenClaw gateway (port 18789). The gateway can run locally or on a remote machine.

- Install on all machines: `npm install -g openclaw`
- For a remote gateway (e.g., Linux laptop reached from Windows), start it with `--bind lan` or expose it via SSH tunnel. The JARVIS Controller auto-spawns the SSH tunnel on Backend Start when `JARVIS_OPENCLAW_URL` points to a remote host.
- Client-side config file: `~/.openclaw/openclaw.json` (or `%APPDATA%\.openclaw\openclaw.json` on Windows). Required keys when talking to a remote gateway:

```json
{
  "gateway": {
    "mode": "remote",
    "remote": {
      "url": "ws://127.0.0.1:18789",
      "transport": "direct",
      "token": "<shared gateway token from the host's openclaw.json>"
    }
  }
}
```

### gog skill (Gmail, Calendar, Drive)

JARVIS delegates mail/calendar/drive actions to the `gog` CLI via OpenClaw.

**Install:**
- macOS/Linux: `brew install steipete/tap/gogcli` or grab a binary from [gogcli releases](https://github.com/steipete/gogcli/releases)
- Windows: download `gogcli_<ver>_windows_amd64.zip` from [gogcli releases](https://github.com/steipete/gogcli/releases) and place `gog.exe` on PATH (e.g. `%USERPROFILE%\.local\bin\`)

**One-time OAuth setup:**
1. Create an OAuth 2.0 client (type: Desktop) in Google Cloud Console and download `client_secret.json`.
2. Register it with gog: `gog auth credentials /path/to/client_secret.json`
3. Authorize your account (opens browser): `gog auth add you@gmail.com --services gmail,calendar,drive,contacts,docs,sheets`
4. Verify: `gog auth list`

**Copying an existing gog config to a new machine:**
- Copy `~/.config/gogcli/` and `~/.config/gog/client_secret.json` to the new machine (`%APPDATA%\gogcli\` and `%APPDATA%\gog\` on Windows).
- OAuth tokens live in the OS keyring (Linux secret-service / Windows Credential Manager / macOS Keychain) and are not portable — re-run `gog auth add` on the new machine.

### Required environment variables (remote OpenClaw)

- `JARVIS_OPENCLAW_URL` — full URL of the remote gateway, e.g. `http://192.168.1.118:18789`
- `JARVIS_OPENCLAW_SSH_HOST` — optional SSH alias (from `~/.ssh/config`) to tunnel through when the gateway is not directly reachable

On Windows, set user-scoped env vars via PowerShell:
```powershell
[Environment]::SetEnvironmentVariable('JARVIS_OPENCLAW_URL', 'http://192.168.1.118:18789', 'User')
```

## Controller App (optional)

`controller/` contains a Tauri desktop app that provides a system-tray launcher and native controls.

```bash
# Development
cd controller && npm install && npm run tauri dev

# Production build
cd controller && npm run tauri build
```

## Docker

```bash
# Standard (PC)
docker-compose up --build

# Raspberry Pi
docker-compose -f docker-compose.rpi.yml up --build
```

## Configuration

Tunable settings (models, ports, audio devices, feature flags) live in `config/config.yaml`. Secrets belong exclusively in `.env` — see [`.env.example`](.env.example) for all supported variables.

## Further Docs

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — system architecture and runtime agents
- [`docs/DESIGN.md`](docs/DESIGN.md) — UI/UX design guidelines and visual language
- [`docs/FRONTEND.md`](docs/FRONTEND.md) — frontend design system and components
- [`docs/PROJECT_DESCRIPTION.md`](docs/PROJECT_DESCRIPTION.md) — full implementation spec
- [`CLAUDE.md`](CLAUDE.md) — contributor conventions, agent workflow, dev commands

## License

MIT License — see LICENSE file for details.
