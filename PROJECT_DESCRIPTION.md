# PROJECT_DESCRIPTION.md — JARVIS AI Assistant

## Vision

Build a fully functional, locally-running AI voice assistant named **JARVIS**, inspired by
Iron Man. The user activates it by saying "Hey JARVIS", speaks a command or question in
German or English, and JARVIS responds with a natural cloned voice. It can answer questions
via Claude API, control the PC, and interact with Smart Home systems.

The project runs:
1. **Locally** (development, any modern PC/Mac/Linux)
2. **Docker** (production, portable)
3. **Raspberry Pi** (always-on home device, ARM64)

---

## Complete Implementation Scope

Implement **all** of the following. Nothing is optional — everything listed here must be
built and working.

---

## 1. Project Bootstrap

### 1.1 Repository Structure
Create the full folder structure as defined in `CLAUDE.md`. All `__init__.py` files must
be present. The project must be importable as a Python package.

### 1.2 Configuration System (`config/config.yaml`)
```yaml
jarvis:
  name: "JARVIS"
  wake_word: "hey jarvis"
  language: "auto"  # auto-detect via whisper

audio:
  input_device_index: null  # null = system default
  sample_rate: 16000
  chunk_size: 1024
  silence_threshold: 500
  silence_duration_ms: 1500  # stop recording after 1.5s silence

stt:
  model: "large-v3"          # "small" on RPi
  device: "cuda"             # "cpu" on RPi
  compute_type: "float16"    # "int8" on RPi
  language: null             # null = auto-detect

tts:
  engine: "xtts"             # "piper" on RPi
  voice_profile: "jarvis"    # filename without extension in voices/
  speed: 1.0
  pitch_shift: 0             # semitones, -4 for darth vader effect
  piper_model: "en_US-lessac-medium"

wake_word:
  model_path: "wake_word/jarvis.onnx"
  threshold: 0.5
  vad_threshold: 0.5

claude:
  model: "claude-sonnet-4-5"
  max_tokens: 300
  temperature: 0.7
  max_history_turns: 10

pc_control:
  enabled: true
  platform: "auto"  # auto, windows, linux

smart_home:
  enabled: false  # enable when Home Assistant is configured

logging:
  level: "INFO"
  file: "logs/jarvis.log"
```

### 1.3 Dependencies

**requirements.txt** (PC / x86_64):
```
anthropic>=0.40.0
faster-whisper>=1.0.0
TTS>=0.22.0                    # Coqui XTTS-v2
openWakeWord>=0.6.0
pyaudio>=0.2.14
sounddevice>=0.4.6
soundfile>=0.12.1
numpy>=1.24.0
scipy>=1.11.0
pydub>=0.25.1
pyautogui>=0.9.54
pycaw>=20181226; sys_platform=="win32"
psutil>=5.9.0
requests>=2.31.0
python-dotenv>=1.0.0
PyYAML>=6.0
loguru>=0.7.0
pytest>=7.4.0
pytest-asyncio>=0.23.0
black>=23.0.0
ruff>=0.1.0
```

**requirements.rpi.txt** (Raspberry Pi / ARM64):
```
anthropic>=0.40.0
faster-whisper>=1.0.0
piper-tts>=1.2.0
openWakeWord>=0.6.0
pyaudio>=0.2.14
sounddevice>=0.4.6
soundfile>=0.12.1
numpy>=1.24.0
scipy>=1.11.0
pydub>=0.25.1
psutil>=5.9.0
requests>=2.31.0
python-dotenv>=1.0.0
PyYAML>=6.0
loguru>=0.7.0
```

---

## 2. Audio Pipeline

### 2.1 Microphone Input (`src/audio/microphone.py`)
- Open audio stream using `sounddevice` (cross-platform, works on RPi).
- Expose `async def stream_audio()` as an async generator yielding raw PCM chunks.
- Respect `config.audio.input_device_index` and `sample_rate`.
- Handle `DeviceNotFoundError` gracefully: log and retry every 5 seconds.

### 2.2 Wake Word Detection (`src/audio/wake_word.py`)
- Use **OpenWakeWord** with the default `hey_jarvis` model (bundled) or a custom `.onnx`.
- Expose `async def listen_for_wake_word(audio_stream) -> bool`.
- On detection: play a short audio chime (embed a base64-encoded `.wav` fallback chime
  so it works without external files).
- Log detection confidence score at DEBUG level.

### 2.3 Speech-to-Text (`src/audio/stt.py`)
- Use **faster-whisper** with model configured in `config.stt`.
- Expose `async def transcribe(audio_data: bytes) -> TranscriptionResult`.
- `TranscriptionResult` dataclass: `text: str`, `language: str`, `confidence: float`.
- Record until silence (use `config.audio.silence_duration_ms`).
- On RPi: automatically downgrade to `small` model and `cpu` + `int8`.

### 2.4 Text-to-Speech (`src/audio/tts.py`)
- Implement a `TTSEngine` abstract base class with `async def speak(text: str)`.
- Implement `XTTSEngine(TTSEngine)` using Coqui XTTS-v2:
  - Load voice from `voices/{voice_profile}.wav` reference file.
  - Synthesize and play via `sounddevice`.
  - Apply pitch shift if `config.tts.pitch_shift != 0` using `scipy`.
- Implement `PiperEngine(TTSEngine)` using Piper TTS:
  - Simpler, CPU-only, for Raspberry Pi.
  - Download model automatically if not present.
- Factory function `create_tts_engine(config) -> TTSEngine` selects the right engine.
- Queue-based: if JARVIS is speaking and a new speak() is called, queue it.
- Expose `async def stop_speaking()` so wake word can interrupt.

---

## 3. Brain / LLM

### 3.1 Claude Client (`src/brain/claude_client.py`)
- Wrap the Anthropic Python SDK.
- Expose `async def chat(message: str, language: str) -> str`.
- Build messages array from conversation history + current message.
- System prompt (see CLAUDE.md "JARVIS Personality" section) must be injected on every call.
- Append detected language to system prompt: "The user is speaking {language}. Respond in {language}."
- Handle `anthropic.APIError`, `anthropic.RateLimitError` with fallback spoken phrases.
- Never raise exceptions to the caller — always return a string.

### 3.2 Conversation Memory (`src/brain/memory.py`)
- Class `ConversationMemory` with:
  - `add_turn(role: str, content: str)` — adds a turn.
  - `get_history() -> list[dict]` — returns last N turns (config `max_history_turns`).
  - `clear()` — resets memory (triggered by "reset" / "clear memory" command).
- In-memory only (no persistence needed in v1).

### 3.3 Intent Parser (`src/brain/intent_parser.py`)
- `async def classify_intent(text: str, language: str) -> Intent`.
- `Intent` enum: `CHAT`, `PC_CONTROL`, `SMART_HOME`, `WEB_SEARCH`, `SYSTEM`.
- Classification via keyword matching (fast, no extra API call):
  - `PC_CONTROL`: open, close, launch, volume, mute, screenshot, type, click (+ German: öffne, schließe, lautstärke)
  - `SMART_HOME`: lights, lamp, thermostat, heizung, licht, lock, unlock
  - `WEB_SEARCH`: search, google, look up, suche, was ist, was bedeutet
  - `SYSTEM`: shutdown, restart, change voice, stimme wechseln, reset, clear memory
  - Everything else → `CHAT`
- Return both intent and extracted parameters (e.g. `{"app": "chrome"}` for PC_CONTROL).

---

## 4. Action Handlers

### 4.1 PC Control (`src/actions/pc_control.py`)
Implement `async def execute_pc_action(intent_data: dict) -> str` returning a confirmation string.

Supported actions:
- **open_app**: launch by name (map common names: "chrome" → `google-chrome` / `chrome.exe`)
  - Maintain a small dict of common app name aliases.
  - Use `subprocess.Popen`, non-blocking.
- **close_app**: find process by name and terminate.
- **set_volume**: 0-100%, use `pycaw` on Windows, `amixer` on Linux.
- **mute_toggle**: toggle system mute.
- **screenshot**: save to Desktop with timestamp filename using `pyautogui`.
- **type_text**: type extracted text using `pyautogui.typewrite`.

Platform detection: auto-detect `sys.platform`, skip unsupported actions gracefully.
On RPi: disable all actions, return `"PC control not available on Raspberry Pi"`.

### 4.2 Smart Home (`src/actions/smart_home.py`)
Implement `async def execute_home_action(intent_data: dict) -> str`.

- HTTP calls to Home Assistant REST API using `httpx` (async).
- Endpoint: `POST /api/services/{domain}/{service}` with entity_id.
- Supported actions:
  - **lights**: turn_on, turn_off, toggle — domain `light`
  - **thermostat**: set temperature — domain `climate`
  - **lock**: lock, unlock — domain `lock`
- If `config.smart_home.enabled = false`, return `"Smart home not configured"`.
- On connection error, return `"Smart home is unavailable"`.

### 4.3 Web Search (`src/actions/web_search.py`)
- Use DuckDuckGo Instant Answer API (no API key needed):
  `GET https://api.duckduckgo.com/?q={query}&format=json&no_html=1`
- Extract `AbstractText` or `Answer` from response.
- Pass result as context to Claude for a natural-language answer.
- Fallback: if no instant answer, Claude answers from its own knowledge.

### 4.4 System Actions (`src/actions/system_actions.py`)
- **change_voice**: update `config.tts.voice_profile`, reload TTS engine.
- **reset_memory**: call `memory.clear()`, speak confirmation.
- **shutdown**: graceful shutdown of main loop.
- **list_voices**: list `.wav` files in `voices/`, speak available profiles.

---

## 5. Main Loop (`src/main.py`)

```
async def main():
    1. Load config + .env
    2. Initialize logger
    3. Initialize TTS engine (pre-warm, takes 10-30s for XTTS)
    4. Speak startup phrase: "JARVIS online. All systems nominal."
    5. Initialize STT model (pre-load)
    6. Initialize ConversationMemory
    7. Start audio stream
    8. Loop forever:
       a. Listen for wake word
       b. On detection: play chime, start recording
       c. Transcribe audio → text + language
       d. If empty/noise: go back to (a)
       e. Classify intent
       f. Route to handler:
          - CHAT → claude_client.chat() → speak response
          - PC_CONTROL → pc_control.execute() → speak confirmation
          - SMART_HOME → smart_home.execute() → speak confirmation
          - WEB_SEARCH → web_search.search() → claude_client.chat(with context) → speak
          - SYSTEM → system_actions.execute()
       g. Add turn to memory
       h. Go back to (a)
```

Handle `KeyboardInterrupt` and `SIGTERM` gracefully — speak "Shutting down. Goodbye, sir."

---

## 6. Docker Setup

### 6.1 `Dockerfile` (PC / x86_64)
```dockerfile
FROM python:3.11-slim

# System deps for audio
RUN apt-get update && apt-get install -y \
    portaudio19-dev \
    libsndfile1 \
    ffmpeg \
    alsa-utils \
    pulseaudio-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Pre-download Whisper model
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('small')"

CMD ["python", "src/main.py"]
```

### 6.2 `Dockerfile.rpi` (Raspberry Pi / ARM64)
```dockerfile
FROM arm64v8/python:3.11-slim

RUN apt-get update && apt-get install -y \
    portaudio19-dev \
    libsndfile1 \
    ffmpeg \
    alsa-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.rpi.txt .
RUN pip install --no-cache-dir -r requirements.rpi.txt

COPY . .

RUN python -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu')"

CMD ["python", "src/main.py"]
```

### 6.3 `docker-compose.yml`
```yaml
version: "3.9"
services:
  jarvis:
    build:
      context: .
      dockerfile: Dockerfile
    env_file: .env
    volumes:
      - ./config:/app/config
      - ./voices:/app/voices
      - ./logs:/app/logs
      - ./wake_word:/app/wake_word
    devices:
      - /dev/snd:/dev/snd           # Audio device passthrough
    environment:
      - PULSE_SERVER=unix:${XDG_RUNTIME_DIR}/pulse/native
    network_mode: host               # Needed for Home Assistant local access
    restart: unless-stopped
```

### 6.4 `docker-compose.rpi.yml`
```yaml
version: "3.9"
services:
  jarvis:
    build:
      context: .
      dockerfile: Dockerfile.rpi
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

## 7. Voice Profiles

### 7.1 Reference Audio Requirements
- Format: `.wav`, 16kHz or 22kHz, mono
- Duration: 6–30 seconds of clean speech
- No background noise, no music

### 7.2 Bundled Profiles (create placeholder scripts)
Create `scripts/download_voices.py` that:
- Downloads a free JARVIS-like voice sample from a public domain source, or
- Generates a neutral English male voice sample using Piper as placeholder
- Saves to `voices/jarvis.wav`

Create `scripts/clone_voice.py` that:
- Takes `--input path/to/reference.wav` and `--name profile_name`
- Copies to `voices/{name}.wav`
- Optionally applies pitch shift for Darth Vader effect (`--pitch -4`)

### 7.3 Pitch Shift Post-Processing
In `tts.py`, after XTTS synthesis, if `config.tts.pitch_shift != 0`:
- Use `librosa.effects.pitch_shift` or `scipy` to shift pitch by N semitones.
- Darth Vader preset: `-4` semitones + slight reverb using `scipy` convolution.

---

## 8. README.md

Write a complete README covering:
1. What JARVIS is (2 sentences)
2. Feature list with emojis
3. Hardware requirements (PC and RPi sections)
4. Hardware shopping list (from CLAUDE.md)
5. Quick Start (local)
6. Quick Start (Docker)
7. Quick Start (Raspberry Pi)
8. How to add a new voice profile
9. How to connect Home Assistant
10. Troubleshooting section (audio device not found, CUDA errors, RPi audio setup)
11. Architecture diagram (ASCII)

---

## 9. Tests (`tests/`)

### `tests/test_tts.py`
- Mock TTS engine, verify `speak()` is called with correct text.
- Test pitch shift is applied when configured.
- Test voice profile loading.

### `tests/test_stt.py`
- Load a sample `.wav` file from `tests/fixtures/`.
- Run through `transcribe()`.
- Assert output is a `TranscriptionResult` with non-empty text.

### `tests/test_intent.py`
- Test intent classification for 20+ sample utterances in DE + EN.
- Assert correct `Intent` enum value for each.
- Test edge cases: empty string, noise transcription, mixed language.

### `tests/test_claude_client.py`
- Mock `anthropic.Anthropic` client.
- Assert system prompt is always included.
- Assert language is injected into system prompt.
- Assert fallback phrase returned on API error.

---

## 10. Implementation Order for Claude Code

Implement in this exact order to allow incremental testing:

1. **Config system** — `config_loader.py`, `config.yaml`, `.env.example`
2. **Logger** — `logger.py`
3. **TTS (Piper first)** — get audio output working immediately
4. **STT** — transcription pipeline
5. **Wake Word** — full listen loop
6. **Claude Client + Memory** — basic chat working end-to-end
7. **Intent Parser** — routing
8. **PC Control** — action handler
9. **Smart Home** — action handler
10. **Web Search** — action handler
11. **System Actions** — voice switching, etc.
12. **Main Loop** — wire everything together
13. **Dockerfile + docker-compose** — containerize
14. **Dockerfile.rpi + docker-compose.rpi.yml** — RPi variant
15. **Tests** — full test suite
16. **README.md** — documentation
17. **scripts/** — helper scripts for voice management

---

## 11. Acceptance Criteria

The project is complete when:

- [ ] `python src/main.py` starts without errors on a modern PC
- [ ] JARVIS speaks the startup phrase on boot
- [ ] Wake word detection works reliably (>90% detection rate in quiet environment)
- [ ] German and English speech is correctly transcribed
- [ ] JARVIS answers questions in the same language as the user
- [ ] At least 3 PC control commands work (open app, set volume, screenshot)
- [ ] Voice profile can be switched via voice command
- [ ] `docker-compose up` starts the full stack
- [ ] `docker-compose -f docker-compose.rpi.yml up` works on ARM64
- [ ] All tests pass: `pytest tests/`
- [ ] No hardcoded secrets anywhere in the codebase
