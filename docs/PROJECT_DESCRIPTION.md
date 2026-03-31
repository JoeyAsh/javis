# PROJECT_DESCRIPTION.md — JARVIS AI Assistant

## Vision
Build a fully functional, locally-running AI voice assistant named **JARVIS**, inspired by Iron Man. The user activates it by saying "Hey JARVIS", speaks a command or question in German or English, and JARVIS responds with a natural cloned voice. It answers questions via the Claude API, controls the PC, and interacts with Smart Home systems.

Runs: locally (development), Docker (production), Raspberry Pi (always-on home device, ARM64).

---

## Implementation Scope

Everything listed here must be built and working.

---

## 1. Project Bootstrap

### 1.1 Repository Structure
Create the full folder structure as defined in `CLAUDE.md`. All `__init__.py` files must be present. The project must be importable as a Python package.

### 1.2 Configuration System (`config/config.yaml`)
```yaml
jarvis:
  name: "JARVIS"
  wake_word: "hey jarvis"
  language: "auto"

audio:
  input_device_index: null
  sample_rate: 16000
  chunk_size: 1024
  silence_threshold: 500
  silence_duration_ms: 1500

stt:
  model: "large-v3"       # "small" on RPi
  device: "cuda"          # "cpu" on RPi
  compute_type: "float16" # "int8" on RPi
  language: null          # auto-detect

tts:
  engine: "xtts"          # "piper" on RPi
  voice_profile: "jarvis"
  speed: 1.0
  pitch_shift: 0
  piper_model: "en_US-lessac-medium"

wake_word:
  model_path: "wake_word/jarvis.onnx"
  threshold: 0.5
  vad_threshold: 0.5

claude:
  model: "claude-sonnet-4-6"
  max_tokens: 300
  temperature: 0.7
  max_history_turns: 10

agents:
  orchestrator_model: "claude-opus-4-5"
  subagent_model: "claude-sonnet-4-6"
  orchestrator_max_tokens: 150
  chat_max_tokens: 300
  action_max_tokens: 100
  skip_orchestrator_on_clear_intent: true
  history_turns_for_chat: 10
  history_turns_for_orchestrator: 3

pc_control:
  enabled: true
  platform: "auto"

smart_home:
  enabled: false

api:
  ws_port: 8765
  http_port: 8766
  cors_origins: ["http://localhost:5173"]

logging:
  level: "INFO"
  file: "logs/jarvis.log"
```

### 1.3 Dependencies

**requirements.txt** (PC / x86_64):
```
anthropic
faster-whisper
TTS
openWakeWord
pyaudio
sounddevice
soundfile
numpy
scipy
pydub
pyautogui
pycaw; sys_platform=="win32"
psutil
httpx
requests
websockets
python-dotenv
PyYAML
loguru
pytest
pytest-asyncio
black
ruff
```

**requirements.rpi.txt** (Raspberry Pi / ARM64):
```
anthropic
faster-whisper
piper-tts
openWakeWord
pyaudio
sounddevice
soundfile
numpy
scipy
pydub
psutil
httpx
requests
websockets
python-dotenv
PyYAML
loguru
```

---

## 2. Audio Pipeline

### 2.1 Microphone Input (`src/audio/microphone.py`)
- Open audio stream using `sounddevice`. Expose `async def stream_audio()` as async generator yielding PCM chunks.
- Respect `config.audio.input_device_index` and `sample_rate`.
- Handle `DeviceNotFoundError`: log and retry every 5 seconds.

### 2.2 Wake Word Detection (`src/audio/wake_word.py`)
- Use **OpenWakeWord** with the default `hey_jarvis` model or custom `.onnx`.
- Expose `async def listen_for_wake_word(audio_stream) -> bool`.
- On detection: play a short audio chime (embed base64-encoded `.wav` fallback).
- Log detection confidence at DEBUG level.

### 2.3 Speech-to-Text (`src/audio/stt.py`)
- Use **faster-whisper** with `config.stt` settings.
- Expose `async def transcribe(audio_data: bytes) -> TranscriptionResult`.
- `TranscriptionResult`: `text: str`, `language: str`, `confidence: float`.
- Record until silence (`config.audio.silence_duration_ms`).
- RPi: auto-downgrade to `small` model, `cpu`, `int8`.

### 2.4 Text-to-Speech (`src/audio/tts.py`)
- `TTSEngine` ABC with `async def speak(text: str)`.
- `XTTSEngine`: Coqui XTTS-v2, loads from `voices/{profile}.wav`, plays via `sounddevice`. Applies pitch shift via `scipy` if configured.
- `PiperEngine`: Piper TTS, CPU-only, auto-downloads model.
- Factory: `create_tts_engine(config) -> TTSEngine`.
- Queue-based speak — new calls queue while speaking. `async def stop_speaking()` for interruption.

---

## 3. Brain / LLM

### 3.1 Claude Client (`src/brain/claude_client.py`)
- Wrap Anthropic Python SDK. Expose `async def chat(message: str, language: str) -> str`.
- Inject JARVIS personality system prompt + language instruction on every call.
- Handle `APIError`, `RateLimitError` with spoken fallback phrases. Never raise to caller.

### 3.2 Conversation Memory (`src/brain/memory.py`)
- `ConversationMemory`: `add_turn(role, content)`, `get_history() -> list[dict]` (last N turns), `clear()`.
- In-memory only (v1).

### 3.3 Intent Parser (`src/brain/intent_parser.py`)
- `async def classify_intent(text: str, language: str) -> Intent`.
- `Intent` enum: `CHAT`, `PC_CONTROL`, `SMART_HOME`, `WEB_SEARCH`, `SYSTEM`.
- Keyword matching (see `docs/ARCHITECTURE.md` for keyword lists).
- Returns intent + extracted parameters.

### 3.4 Orchestrator (`src/brain/orchestrator.py`)
- Model: `claude-opus-4-5`. Routes ambiguous/multi-step requests to subagents.
- See `docs/ARCHITECTURE.md` for full spec.

### 3.5 Subagents (`src/brain/agents/`)
- All use `claude-sonnet-4-6`. Inherit from `BaseAgent`.
- `ChatAgent`, `PcAgent`, `SmartHomeAgent`, `SearchAgent`, `SystemAgent`.
- See `docs/ARCHITECTURE.md` for details.

---

## 4. Action Handlers

### 4.1 PC Control (`src/actions/pc_control.py`)
`async def execute_pc_action(intent_data: dict) -> str`
- `open_app`: `subprocess.Popen`, common name aliases dict (chrome, spotify, etc.)
- `close_app`: find process by name and terminate.
- `set_volume`: `pycaw` (Windows), `amixer` (Linux). Range 0–100.
- `mute_toggle`: toggle system mute.
- `screenshot`: save to Desktop with timestamp via `pyautogui`.
- `type_text`: `pyautogui.typewrite`.
- RPi: all actions return `"PC control not available on Raspberry Pi"`.

### 4.2 Smart Home (`src/actions/smart_home.py`)
`async def execute_home_action(intent_data: dict) -> str`
- `httpx` async HTTP to Home Assistant REST API.
- Endpoint: `POST /api/services/{domain}/{service}` with `entity_id`.
- Supported: lights (turn_on/off/toggle), thermostat (set_temperature), lock (lock/unlock).
- Returns `"Smart home not configured"` if disabled, `"Smart home is unavailable"` on error.

### 4.3 Web Search (`src/actions/web_search.py`)
- DuckDuckGo Instant Answer API (no key): `GET https://api.duckduckgo.com/?q={query}&format=json&no_html=1`
- Extract `AbstractText` or `Answer` → pass as context to Claude for natural-language reply.
- Fallback: Claude answers from own knowledge if no instant answer.

### 4.4 System Actions (`src/actions/system_actions.py`)
- `change_voice`: update `config.tts.voice_profile`, reload TTS engine.
- `reset_memory`: `memory.clear()` + speak confirmation.
- `shutdown`: graceful shutdown of main loop.
- `list_voices`: list `.wav` files in `voices/`, speak available profiles.

---

## 5. WebSocket API (`src/api/ws_server.py`)
- Library: `websockets` (async).
- Port: `config.api.ws_port` (default 8765). HTTP port: 8766 for `GET /voices`.
- Broadcasts: `state` on OrbState change, `transcript` after STT + JARVIS response, `system` metrics every 5s via `psutil`.
- Receives: `set_voice`, `reset` commands → dispatches to SystemAgent.
- Run alongside main loop via `asyncio.gather`.

---

## 6. Main Loop (`src/main.py`)
```
async def main():
  1. Load config + .env
  2. Init logger
  3. Init TTS engine (pre-warm)
  4. Speak: "JARVIS online. All systems nominal."
  5. Init STT model
  6. Init ConversationMemory
  7. Start WebSocket server (asyncio.gather)
  8. Start audio stream
  9. Loop:
     a. Listen for wake word
     b. Play chime, start recording
     c. Transcribe → text + language
     d. If empty/noise → back to (a)
     e. Classify intent
     f. If ambiguous/multi-step → Orchestrator; else → direct subagent
     g. Execute → speak AgentResult.spoken_response
     h. Add turn to memory, broadcast transcript via WS
     i. Back to (a)
```
Handle `KeyboardInterrupt` + `SIGTERM`: speak "Shutting down. Goodbye, sir."

---

## 7. Docker Setup

### `Dockerfile` (x86_64)
```dockerfile
FROM python:3.11-slim
RUN apt-get update && apt-get install -y \
    portaudio19-dev libsndfile1 ffmpeg alsa-utils pulseaudio-utils \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('small')"
COPY . .
CMD ["python", "src/main.py"]
```

### `Dockerfile.rpi` (ARM64)
```dockerfile
FROM arm64v8/python:3.11-slim
RUN apt-get update && apt-get install -y \
    portaudio19-dev libsndfile1 ffmpeg alsa-utils \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.rpi.txt .
RUN pip install --no-cache-dir -r requirements.rpi.txt
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu')"
COPY . .
CMD ["python", "src/main.py"]
```

### `docker-compose.yml`
```yaml
version: "3.9"
services:
  jarvis:
    build: { context: ., dockerfile: Dockerfile }
    env_file: .env
    volumes:
      - ./config:/app/config
      - ./voices:/app/voices
      - ./logs:/app/logs
      - ./wake_word:/app/wake_word
    devices:
      - /dev/snd:/dev/snd
    environment:
      - PULSE_SERVER=unix:${XDG_RUNTIME_DIR}/pulse/native
    network_mode: host
    restart: unless-stopped
```

### `docker-compose.rpi.yml`
```yaml
version: "3.9"
services:
  jarvis:
    build: { context: ., dockerfile: Dockerfile.rpi }
    env_file: .env
    volumes:
      - ./config:/app/config
      - ./voices:/app/voices
      - ./logs:/app/logs
    devices:
      - /dev/snd:/dev/snd
    environment:
      - JARVIS_PLATFORM=rpi
    network_mode: host
    restart: unless-stopped
```

---

## 8. Frontend
See `docs/FRONTEND.md` for full spec. React 18 + TypeScript + Vite + Tailwind + Three.js particle orb, WebSocket-connected to Python backend.

---

## 9. Voice Profiles

- Format: `.wav`, 16–22kHz, mono, 6–30s clean speech.
- `scripts/download_voices.py`: downloads or generates a placeholder `voices/jarvis.wav`.
- `scripts/clone_voice.py`: `--input ref.wav --name profile_name [--pitch -4]` → copies to `voices/{name}.wav`.
- Pitch shift in `tts.py`: `librosa` or `scipy`. Darth Vader preset: `-4` semitones + reverb.

---

## 10. Tests (`tests/`)

- `test_tts.py`: mock TTS, verify `speak()` called with correct text, pitch shift applied, voice profile loading.
- `test_stt.py`: transcribe a fixture `.wav` → assert `TranscriptionResult` with non-empty text.
- `test_intent.py`: 20+ DE+EN utterances → correct `Intent` enum. Edge cases: empty string, noise, mixed language.
- `test_claude_client.py`: mock Anthropic client. Assert system prompt included, language injected, fallback returned on error.

---

## 11. README.md
Cover: what JARVIS is, feature list, hardware requirements (PC + RPi), quick start (local/Docker/RPi), how to add a voice profile, how to connect Home Assistant, troubleshooting (audio device, CUDA, RPi audio), ASCII architecture diagram.

---

## 12. Implementation Order

1. Config system (`config_loader.py`, `config.yaml`, `.env.example`)
2. Logger (`logger.py`)
3. TTS — Piper first (get audio output immediately)
4. STT
5. Wake Word
6. Claude Client + Memory
7. Intent Parser
8. Orchestrator + Subagents
9. WebSocket Server
10. PC Control
11. Smart Home
12. Web Search
13. System Actions
14. Main Loop
15. Docker + docker-compose
16. Dockerfile.rpi + docker-compose.rpi.yml
17. Frontend (React + Three.js orb)
18. Tests
19. README.md
20. Voice scripts

---

## 13. Acceptance Criteria

- [ ] `python src/main.py` starts without errors
- [ ] JARVIS speaks startup phrase on boot
- [ ] Wake word detection works (>90% in quiet environment)
- [ ] DE + EN speech correctly transcribed
- [ ] JARVIS responds in user's language
- [ ] 3+ PC control commands work (open app, set volume, screenshot)
- [ ] Voice profile switchable via voice command
- [ ] Frontend orb reacts to JARVIS state in real-time
- [ ] `docker-compose up` starts full stack
- [ ] `docker-compose -f docker-compose.rpi.yml up` works on ARM64
- [ ] All tests pass: `pytest tests/`
- [ ] No hardcoded secrets anywhere
