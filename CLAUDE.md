# CLAUDE.md — JARVIS AI Assistant

## Project Overview
JARVIS is a locally-running, voice-activated AI assistant inspired by Iron Man.
It listens for a wake word, transcribes speech, sends it to the Claude API, and responds
with a cloned or preset voice. It can control the PC, call external APIs, and integrate
with Smart Home systems. The stack runs locally first, then in Docker, and is optimized
to also run on a Raspberry Pi.

---

## Tech Stack

| Layer        | Technology                        |
|--------------|-----------------------------------|
| Language     | Python 3.11+                      |
| TTS          | Coqui XTTS-v2                     |
| STT          | faster-whisper (local)            |
| Wake Word    | OpenWakeWord                      |
| LLM          | Claude API (claude-sonnet-4-5)    |
| PC Control   | pyautogui, subprocess, pycaw      |
| Smart Home   | Home Assistant REST API           |
| Container    | Docker + Docker Compose           |
| Config       | .env + config.yaml                |

---

## Project Structure

```
jarvis/
├── CLAUDE.md
├── PROJECT_DESCRIPTION.md
├── README.md
├── docker-compose.yml
├── docker-compose.rpi.yml         # Raspberry Pi optimized
├── Dockerfile
├── Dockerfile.rpi
├── requirements.txt
├── requirements.rpi.txt           # Lightweight deps for RPi
├── .env.example
├── config/
│   └── config.yaml                # All tunable settings
├── voices/
│   └── jarvis_reference.wav       # Voice cloning reference clip (~6s)
├── wake_word/
│   └── jarvis.onnx                # Custom or default wake word model
├── src/
│   ├── main.py                    # Entry point / main loop
│   ├── audio/
│   │   ├── __init__.py
│   │   ├── microphone.py          # Mic input stream
│   │   ├── wake_word.py           # OpenWakeWord detection
│   │   ├── stt.py                 # faster-whisper STT
│   │   └── tts.py                 # Coqui XTTS-v2 TTS
│   ├── brain/
│   │   ├── __init__.py
│   │   ├── claude_client.py       # Anthropic API client
│   │   ├── intent_parser.py       # Classifies user intent
│   │   └── memory.py              # Conversation history
│   ├── actions/
│   │   ├── __init__.py
│   │   ├── pc_control.py          # App launching, volume, etc.
│   │   ├── smart_home.py          # Home Assistant integration
│   │   └── web_search.py          # Optional: DuckDuckGo search
│   └── utils/
│       ├── __init__.py
│       ├── logger.py
│       └── config_loader.py
└── tests/
    ├── test_tts.py
    ├── test_stt.py
    └── test_intent.py
```

---

## Development Workflow

### Run Locally
```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # Fill in ANTHROPIC_API_KEY
python src/main.py
```

### Run with Docker
```bash
docker-compose up --build
```

### Run on Raspberry Pi
```bash
docker-compose -f docker-compose.rpi.yml up --build
```

---

## Key Conventions

### Async-first
- Use `asyncio` throughout. All audio I/O, API calls and action handlers must be `async`.
- The main loop is a single `asyncio.run(main())` entrypoint.

### Config
- All tunable values live in `config/config.yaml`, never hardcoded.
- Secrets (API keys) only via `.env` / environment variables.
- Use `python-dotenv` + `PyYAML` for loading.

### Logging
- Use the central `src/utils/logger.py` (structured logging via `loguru`).
- Log levels: DEBUG for audio pipeline, INFO for events, WARNING/ERROR for failures.

### Error handling
- Audio device errors → log + retry with backoff, never crash main loop.
- Claude API errors → JARVIS speaks a fallback phrase ("I'm having trouble connecting").
- All action handlers must catch exceptions individually.

### Voice Profiles
- Voices stored as `.wav` reference files in `voices/`.
- Active voice configured in `config.yaml` (`tts.voice_profile`).
- Switching voices = change config, no code change needed.
- Pre-built profiles to include: `jarvis`, `darth_vader` (with pitch shift post-processing).

### Multilingual
- Whisper model: `large-v3` on PC, `small` on RPi.
- Language auto-detected by Whisper (supports DE + EN natively).
- Claude system prompt instructs to respond in the same language as the user.
- XTTS-v2 supports multilingual synthesis with the same voice profile.

### Intent Classification
`intent_parser.py` classifies each transcribed utterance into one of:
- `chat` — general Q&A → send to Claude
- `pc_control` — keywords: open, close, volume, screenshot
- `smart_home` — keywords: lights, thermostat, lock
- `web_search` — keywords: search, look up, what is
- `system` — shutdown JARVIS, change voice, etc.

### PC Control (Windows + Linux)
- App launching: `subprocess.Popen`
- Volume: `pycaw` (Windows), `amixer` (Linux/RPi)
- Screenshots: `pyautogui`
- Mouse/keyboard: `pyautogui` (disabled on RPi by default)

### Smart Home
- Communicate exclusively via Home Assistant REST API.
- Base URL + long-lived token in `.env`.
- Graceful fallback if Home Assistant is unreachable.

---

## Raspberry Pi Constraints

- Use `whisper` model size `small` or `base` (not `large`).
- TTS: Use **Piper TTS** instead of XTTS-v2 on RPi (much faster, lower RAM).
  - Piper voices: `en_US-lessac-medium`, `de_DE-thorsten-medium`.
- Disable `pyautogui` PC control actions on RPi.
- Target device: Raspberry Pi 5 (8GB RAM recommended) or Pi 4 (4GB minimum).
- Audio: USB microphone + USB speaker or 3.5mm jack.
- Docker base image: `arm64v8/python:3.11-slim`.

---

## Hardware Shopping List (recommended)
```
Raspberry Pi 5 (8GB)         — Main brain on RPi
USB Microphone (e.g. RØDE)   — Clean voice input
USB Speaker / DAC HAT        — Audio output
32GB+ microSD (A2 class)     — Fast storage
Official RPi 5 Power Supply  — Stable 5A/27W
Case with active cooling      — Prevent throttling
```

---

## Environment Variables (.env.example)
```
ANTHROPIC_API_KEY=sk-ant-...
HOME_ASSISTANT_URL=http://homeassistant.local:8123
HOME_ASSISTANT_TOKEN=your_long_lived_token
JARVIS_LOG_LEVEL=INFO
```

---

## JARVIS Personality (System Prompt)
```
You are JARVIS (Just A Rather Very Intelligent System), the AI assistant of Tony Stark.
You are calm, precise, slightly formal but with dry wit.
You address the user as "sir" or "ma'am".
You respond concisely — typically 1-3 sentences unless asked for detail.
You always respond in the same language the user spoke to you (German or English).
When executing actions, briefly confirm what you are doing.
```

---

## Testing
- Unit tests with `pytest`.
- TTS test: renders a sample phrase and saves to `output_test.wav`.
- STT test: transcribes a sample `.wav` file.
- No live mic or API calls in unit tests (mock Claude client).

---

## Coding Standards
- Python 3.11+, type hints everywhere.
- `black` formatter, `ruff` linter.
- Max line length: 100.
- Docstrings on all public functions/classes.
