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
