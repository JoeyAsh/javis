# JARVIS — Architecture

## Runtime Flow

```
User speaks → STT → intent_parser.py (keyword match, no LLM)
    ↓ ambiguous/multi-step         ↓ clear single intent
Orchestrator (Opus)           skip to subagent directly
    ↓ OrchestratorDecision(s)
    ├─ chat        → ChatAgent       → Claude API
    ├─ pc          → PcAgent         → pc_control.py
    ├─ smart_home  → SmartHomeAgent  → Home Assistant REST
    ├─ search      → SearchAgent     → DuckDuckGo → Claude summarizes
    └─ system      → SystemAgent     → config/memory/shutdown
    ↓ AgentResult.spoken_response → TTS
```

## Orchestrator (`src/brain/orchestrator.py`)
Model: `claude-opus-4-5`. Input: transcribed text + language + last-3-turns summary.
Returns `OrchestratorDecision` (JSON):
```python
@dataclass
class OrchestratorDecision:
    agent: str            # "chat" | "pc" | "smart_home" | "search" | "system"
    task: str
    params: dict          # e.g. {"app": "chrome"}
    requires_followup: bool
    reasoning: str        # logged only, never spoken
```
Rules: never answer directly — only route. Decompose multi-step requests into ordered decisions. Resolve pronouns from history ("turn it off" → last mentioned device).

## Subagents
```python
class BaseAgent(ABC):
    model: str = "claude-sonnet-4-6"
    async def run(self, task: str, params: dict, language: str) -> AgentResult: ...

@dataclass
class AgentResult:
    spoken_response: str
    success: bool
    data: dict
```

| Agent | Purpose | Notes |
|---|---|---|
| ChatAgent | General Q&A | Full JARVIS personality, last-10-turns history |
| PcAgent | PC control | subprocess, pycaw, pyautogui (disabled on RPi) |
| SmartHomeAgent | Home Assistant | HA REST API, graceful fallback if unreachable |
| SearchAgent | Web search | DuckDuckGo → Claude summarizes → 1-2 sentences |
| SystemAgent | JARVIS system | Voice change, memory clear, shutdown |

## Cost Optimization
- Orchestrator gets last-3-turns summary only. ChatAgent gets last-10-turns. All others: no history.
- `intent_parser.py` runs before Orchestrator — skips it on high-confidence single intent.
- Max tokens: Orchestrator `150`, ChatAgent `300`, all others `100`.

```yaml
agents:
  orchestrator_model: "claude-opus-4-5"
  subagent_model: "claude-sonnet-4-6"
  orchestrator_max_tokens: 150
  chat_max_tokens: 300
  action_max_tokens: 100
  skip_orchestrator_on_clear_intent: true
  history_turns_for_chat: 10
  history_turns_for_orchestrator: 3
```

## Intent Classification (`intent_parser.py`)
Keyword matching, no LLM:
- `chat` → general Q&A
- `pc_control` → open, close, volume, screenshot, öffne, lautstärke
- `smart_home` → lights, thermostat, lock, licht, heizung
- `web_search` → search, look up, what is, suche, was ist
- `system` → shutdown JARVIS, change voice, stimme wechseln, reset

## Voice & Multilingual
- Voice profiles: `.wav` files in `voices/`. Active profile: `config.yaml` → `tts.voice_profile`.
- Built-in: `jarvis`, `darth_vader` (pitch shift: -4 semitones).
- Language: Whisper auto-detects DE/EN. Claude system prompt mirrors detected language. XTTS-v2 synthesizes in same language.

## JARVIS Personality (ChatAgent system prompt)
```
You are JARVIS (Just A Rather Very Intelligent System).
Calm, precise, slightly formal, dry wit. Address user as "sir" or "ma'am".
Respond in 1-3 sentences unless asked for detail.
Always respond in the same language the user spoke. Briefly confirm actions.
```

## Raspberry Pi Constraints
- STT: Whisper `small` or `base` only (no CUDA).
- TTS: Piper TTS instead of XTTS-v2 (`en_US-lessac-medium`, `de_DE-thorsten-medium`).
- Disable all `pyautogui` PC actions.
- Hardware: RPi 5 (8GB recommended), RPi 4 (4GB min). Docker: `arm64v8/python:3.11-slim`.
- Audio: USB mic + USB speaker or 3.5mm jack.
