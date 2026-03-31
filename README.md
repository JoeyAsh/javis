# JARVIS

JARVIS (Just A Rather Very Intelligent System) is a voice-activated AI assistant that runs locally on your PC or Raspberry Pi. It uses wake word detection, speech-to-text, Claude AI for natural language understanding, and text-to-speech with voice cloning to provide a conversational interface. JARVIS can control your PC, manage smart home devices via Home Assistant, search the web, and engage in general conversation.

## Features

- **Wake Word Detection**: "Hey JARVIS" activation using OpenWakeWord
- **Multilingual Support**: Automatic English/German detection and response
- **Voice Cloning**: Custom voice profiles using XTTS-v2 (PC) or Piper TTS (RPi)
- **PC Control**: Open/close apps, adjust volume, take screenshots, type text
- **Smart Home Integration**: Control lights, thermostats, and locks via Home Assistant
- **Web Search**: DuckDuckGo search with AI-powered summaries
- **Conversation Memory**: Context-aware responses with conversation history
- **Real-time Frontend**: Three.js particle orb visualization with WebSocket communication
- **Cost-Optimized**: Intent classification skips LLM calls when possible

## Hardware Requirements

### PC (Recommended)
- **CPU**: Modern multi-core processor
- **GPU**: NVIDIA GPU with 4GB+ VRAM (for CUDA acceleration)
- **RAM**: 8GB minimum, 16GB recommended
- **Audio**: USB microphone + speakers/headphones

### Raspberry Pi
- **Model**: Raspberry Pi 5 (8GB) recommended, RPi 4 (4GB) minimum
- **Storage**: 32GB+ microSD card
- **Audio**: USB microphone + USB speaker or 3.5mm audio jack
- **Note**: Uses CPU-only inference with smaller models

## Quick Start

### Local Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/jarvis.git
cd jarvis

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Generate voice profiles
python scripts/download_voices.py

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Run JARVIS
python src/main.py
```

### Docker (PC)

```bash
# Build and run
docker-compose up --build

# Run in background
docker-compose up -d
```

### Docker (Raspberry Pi)

```bash
# Build and run on RPi
docker-compose -f docker-compose.rpi.yml up --build
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# Open http://localhost:5173
```

## Configuration

### Environment Variables (.env)

```bash
ANTHROPIC_API_KEY=sk-ant-...
HOME_ASSISTANT_URL=http://homeassistant.local:8123
HOME_ASSISTANT_TOKEN=your-long-lived-access-token
```

### Config File (config/config.yaml)

Key settings:
- `stt.model`: Whisper model size (large-v3 for PC, small for RPi)
- `tts.engine`: xtts for PC, piper for RPi
- `tts.voice_profile`: Voice profile name from voices/ directory
- `api.ws_port`: WebSocket port (default: 8765)
- `api.http_port`: HTTP API port (default: 8766)

## Adding a Voice Profile

1. Record 10-30 seconds of clear speech in a quiet environment
2. Save as WAV file (16kHz or higher)
3. Run the clone script:

```bash
python scripts/clone_voice.py --input your_recording.wav --name my_voice

# With pitch shift for Darth Vader effect:
python scripts/clone_voice.py --input your_recording.wav --name vader --pitch -4
```

4. Update config:
```yaml
tts:
  voice_profile: "my_voice"
```

## Connecting Home Assistant

1. In Home Assistant, go to Profile > Long-Lived Access Tokens
2. Create a new token and copy it
3. Add to .env:
```bash
HOME_ASSISTANT_URL=http://your-ha-ip:8123
HOME_ASSISTANT_TOKEN=your-token
```
4. Enable in config:
```yaml
smart_home:
  enabled: true
```

## Troubleshooting

### Audio Device Not Found

```bash
# List available audio devices
python -c "import sounddevice as sd; print(sd.query_devices())"

# Set specific device in config/config.yaml
audio:
  input_device_index: 1  # Use device index from list
```

### CUDA/GPU Errors

```bash
# Verify CUDA installation
python -c "import torch; print(torch.cuda.is_available())"

# Fall back to CPU in config
stt:
  device: "cpu"
  compute_type: "int8"
```

### Raspberry Pi Audio Issues

```bash
# Check ALSA devices
arecord -l
aplay -l

# Test microphone
arecord -d 5 -f S16_LE -r 16000 test.wav
aplay test.wav

# Set audio device in config if needed
audio:
  input_device_index: 0
```

### WebSocket Connection Failed

- Ensure backend is running on correct ports
- Check firewall allows ports 8765 and 8766
- For RPi: connect frontend to `ws://<rpi-ip>:8765`

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         User                                    │
│                          │                                      │
│                          ▼                                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Audio Input                          │   │
│  │  ┌──────────────┐   ┌────────────┐   ┌──────────────┐  │   │
│  │  │  Microphone  │ → │ Wake Word  │ → │    STT       │  │   │
│  │  │              │   │ Detection  │   │  (Whisper)   │  │   │
│  │  └──────────────┘   └────────────┘   └──────────────┘  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                          │                                      │
│                          ▼                                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                   Intent Parser                          │   │
│  │             (Keyword matching, no LLM)                   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                          │                                      │
│           ┌──────────────┴──────────────┐                      │
│           ▼                              ▼                      │
│  ┌─────────────────┐          ┌─────────────────┐              │
│  │   Orchestrator  │          │  Direct Route   │              │
│  │  (Claude Opus)  │          │ (High Conf.)    │              │
│  └─────────────────┘          └─────────────────┘              │
│           │                              │                      │
│           └──────────────┬───────────────┘                      │
│                          ▼                                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Subagents                            │   │
│  │  ┌────────┐ ┌────────┐ ┌──────────┐ ┌────────┐ ┌─────┐ │   │
│  │  │  Chat  │ │   PC   │ │  Smart   │ │ Search │ │Sys- │ │   │
│  │  │ Agent  │ │ Agent  │ │  Home    │ │ Agent  │ │tem  │ │   │
│  │  │        │ │        │ │  Agent   │ │        │ │Agent│ │   │
│  │  └────────┘ └────────┘ └──────────┘ └────────┘ └─────┘ │   │
│  └─────────────────────────────────────────────────────────┘   │
│                          │                                      │
│                          ▼                                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                   Audio Output                          │   │
│  │  ┌───────────────────────┐   ┌───────────────────────┐ │   │
│  │  │   TTS (XTTS/Piper)    │ → │      Speakers         │ │   │
│  │  └───────────────────────┘   └───────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────┘   │
│                          │                                      │
│                          ▼                                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │               WebSocket Server                          │   │
│  │  ┌────────────┐   ┌────────────┐   ┌────────────────┐  │   │
│  │  │   State    │   │ Transcript │   │ System Metrics │  │   │
│  │  │ Broadcast  │   │  Broadcast │   │    Broadcast   │  │   │
│  │  └────────────┘   └────────────┘   └────────────────┘  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                          │                                      │
│                          ▼                                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                     Frontend                            │   │
│  │  ┌──────────────────────────────────────────────────┐  │   │
│  │  │           Three.js Particle Orb                  │  │   │
│  │  │    ┌──────────┐ ┌──────────┐ ┌──────────────┐   │  │   │
│  │  │    │  Status  │ │Transcript│ │    Voice     │   │  │   │
│  │  │    │   Bar    │ │   Feed   │ │   Selector   │   │  │   │
│  │  │    └──────────┘ └──────────┘ └──────────────┘   │  │   │
│  │  └──────────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## License

MIT License - see LICENSE file for details.
