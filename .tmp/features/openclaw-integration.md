# Feature Spec: OpenClaw Integration

## Status
Planned — awaiting implementation authorization

## Summary
Integrate OpenClaw as the agent-runtime backbone for JARVIS. OpenClaw handles all agent routing, tool execution, memory, and third-party integrations (Gmail, Spotify, GitHub, smart home), while JARVIS retains ownership of the voice pipeline (wake word, STT, TTS), the 3D orb HUD, and the multi-monitor panel system.

## Goals
- Run OpenClaw gateway as a managed subprocess or systemd service alongside JARVIS
- Route conversational queries from JARVIS to OpenClaw agent sessions
- Leverage OpenClaw's 50+ built-in integrations instead of building custom clients
- Migrate JARVIS persona to OpenClaw's `SOUL.md` workspace file
- Maintain sub-3s voice round-trip latency through the OpenClaw layer
- Preserve full ownership of JARVIS-unique capabilities (voice UX, HUD, Fish Audio TTS)

## Non-Goals
- Replacing OpenWakeWord or faster-whisper with OpenClaw's voice mode (Linux/RPi not supported)
- Replacing Fish Audio TTS with ElevenLabs (German voice quality requirement)
- Running OpenClaw in Docker (JARVIS backend already Dockerized; OpenClaw runs on host or in sidecar)
- Multi-user session isolation (JARVIS is single-user)
- ClawHub skill publishing (MVP focuses on consumption, not contribution)

---

## Architecture Decision

### Recommended: Option A — Full Backbone

OpenClaw handles ALL agent routing, tools, memory, and integrations. JARVIS becomes a voice/HUD bridge.

**Rationale:**
- Eliminates ~60% of planned JARVIS integration code (Gmail, Calendar, Spotify, GitHub, smart home)
- OpenClaw's 50+ channel integrations are production-tested
- Unified memory system replaces our `jarvis-memory-db.md` for conversational context
- Skill system replaces our `claude-code-integration.md` self-modification idea
- Multi-model support future-proofs provider switching

**What JARVIS keeps:**
- Wake word detection (OpenWakeWord) — OpenClaw has no Linux wake word support
- STT (faster-whisper) — German low-latency requirement
- TTS (Fish Audio) — German voice quality requirement
- 3D orb visualization + all HUD panels (React/Three.js)
- Multi-monitor panel layout persistence
- Voice UX orchestration (barge-in, fillers, streaming)
- `jarvis-memory-db.md` scoped to UI state only (panel prefs, layout, transcript history)

**What moves to OpenClaw:**
- All Claude API calls for conversational intelligence
- Gmail, Google Calendar integrations
- Spotify integration
- GitHub/Docker/CI monitoring
- Smart home (Philips Hue via OpenClaw; Govee may need custom skill)
- Conversational memory and fact storage
- Proactive scheduling (via OpenClaw cron/standing orders)
- Self-debugging/code-fixing (via OpenClaw skill system)

### Alternative Options (Not Recommended for MVP)

**Option B — Hybrid:**
Use OpenClaw only for specific tools (channels, browser); keep JARVIS orchestrator for the rest.
- Pro: Less migration risk
- Con: Maintains two agent systems; duplicated complexity

**Option C — Channel Only:**
Use OpenClaw solely to dispatch messages to WhatsApp/Telegram/etc.; everything else JARVIS-native.
- Pro: Minimal integration
- Con: Misses the main value proposition (agent runtime, memory, tools)

---

## Technical Design

### Installation Path

#### Prerequisites
- Node.js 24+ (or 22.16+) on the host system
- `ANTHROPIC_API_KEY` or OpenAI API key configured

#### Installation Script (`scripts/install_openclaw.sh`)
```bash
#!/bin/bash
set -e

# Install OpenClaw globally
npm install -g openclaw@latest

# Run onboarding (creates ~/.openclaw/ directory structure)
openclaw onboard

# Install daemon (systemd on Linux, launchd on macOS)
openclaw onboard --install-daemon

# Verify installation
openclaw doctor
```

#### JARVIS Installer Integration
Add to `scripts/install.sh` or Docker entrypoint:
```bash
# Check if OpenClaw is available
if ! command -v openclaw &> /dev/null; then
    echo "Installing OpenClaw..."
    ./scripts/install_openclaw.sh
fi

# Verify daemon is running
openclaw doctor || echo "WARNING: OpenClaw daemon not running"
```

### Configuration

#### OpenClaw Config (`~/.openclaw/openclaw.json`)
```json
{
  "agent": {
    "model": "anthropic/claude-sonnet-4-6"
  },
  "gateway": {
    "port": 18789
  },
  "channels": {
    "whatsapp": {
      "enabled": false
    },
    "telegram": {
      "enabled": false
    }
  },
  "memory": {
    "engine": "builtin"
  },
  "security": {
    "dmPolicy": "pairing"
  }
}
```

#### .env.example Additions
```bash
# OpenClaw
OPENCLAW_GATEWAY_URL=http://127.0.0.1:18789
OPENCLAW_GATEWAY_PORT=18789

# Model provider (OpenClaw uses this)
ANTHROPIC_API_KEY=sk-ant-...
# OR
OPENAI_API_KEY=sk-...
```

#### config.yaml Additions
```yaml
openclaw:
  enabled: true
  gateway_url: "http://127.0.0.1:18789"
  gateway_port: 18789
  managed_daemon: false  # true = JARVIS starts/stops daemon; false = assume systemd
  health_check_interval_seconds: 30
  session_id: "jarvis-main"
  thinking_level: "normal"  # "none" | "normal" | "high"
  timeout_seconds: 30
```

### OpenClawClient (`src/integrations/openclaw/client.py`)

```python
from dataclasses import dataclass
from typing import Any
import asyncio
import subprocess
import httpx

@dataclass
class AgentResponse:
    """Response from OpenClaw agent query."""
    text: str
    session_id: str
    thinking_used: bool
    tool_calls: list[dict[str, Any]]
    error: str | None = None

@dataclass
class SessionInfo:
    """OpenClaw session information."""
    session_id: str
    created_at: str
    message_count: int
    model: str

class OpenClawClient:
    """Async client for OpenClaw gateway interaction."""

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize OpenClaw client.
        
        Args:
            config: openclaw section from config.yaml
        """
        self._config = config
        self._gateway_url = config.get("gateway_url", "http://127.0.0.1:18789")
        self._session_id = config.get("session_id", "jarvis-main")
        self._thinking = config.get("thinking_level", "normal")
        self._timeout = config.get("timeout_seconds", 30)
        self._http: httpx.AsyncClient | None = None

    async def initialize(self) -> None:
        """Initialize client and verify gateway connection.
        
        Raises:
            OpenClawConnectionError: If gateway is not reachable
        """
        self._http = httpx.AsyncClient(
            base_url=self._gateway_url,
            timeout=self._timeout,
        )
        
        # Health check
        if not await self.is_healthy():
            raise OpenClawConnectionError(
                f"OpenClaw gateway not reachable at {self._gateway_url}"
            )

    async def close(self) -> None:
        """Close HTTP client."""
        if self._http:
            await self._http.aclose()

    async def is_healthy(self) -> bool:
        """Check if OpenClaw gateway is running and healthy."""
        try:
            # Use CLI doctor command for health check
            proc = await asyncio.create_subprocess_exec(
                "openclaw", "doctor",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            await proc.wait()
            return proc.returncode == 0
        except FileNotFoundError:
            return False

    async def query_agent(
        self,
        message: str,
        session_id: str | None = None,
        thinking: str | None = None,
    ) -> AgentResponse:
        """Query the OpenClaw agent.
        
        Args:
            message: User message to send
            session_id: Session ID (default: configured session)
            thinking: Thinking level override ("none", "normal", "high")
            
        Returns:
            AgentResponse with text and metadata
        """
        session = session_id or self._session_id
        think_level = thinking or self._thinking
        
        # Use CLI for now (subprocess); switch to REST when available
        cmd = [
            "openclaw", "agent",
            "--message", message,
            "--session", session,
            "--thinking", think_level,
            "--json",  # Request JSON output
        ]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=self._timeout,
        )
        
        if proc.returncode != 0:
            return AgentResponse(
                text="",
                session_id=session,
                thinking_used=False,
                tool_calls=[],
                error=stderr.decode(),
            )
        
        # Parse JSON response
        import json
        try:
            data = json.loads(stdout.decode())
            return AgentResponse(
                text=data.get("response", ""),
                session_id=session,
                thinking_used=data.get("thinking_used", False),
                tool_calls=data.get("tool_calls", []),
            )
        except json.JSONDecodeError:
            # Fallback: treat stdout as plain text
            return AgentResponse(
                text=stdout.decode().strip(),
                session_id=session,
                thinking_used=False,
                tool_calls=[],
            )

    async def send_message(
        self,
        channel: str,
        to: str,
        text: str,
    ) -> bool:
        """Send a message via OpenClaw channel.
        
        Args:
            channel: Channel name (whatsapp, telegram, slack, etc.)
            to: Recipient identifier
            text: Message text
            
        Returns:
            True if sent successfully
        """
        cmd = [
            "openclaw", "message", "send",
            "--channel", channel,
            "--to", to,
            "--message", text,
        ]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        await proc.wait()
        return proc.returncode == 0

    async def list_sessions(self) -> list[SessionInfo]:
        """List all active sessions."""
        cmd = ["openclaw", "sessions", "list", "--json"]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        
        import json
        try:
            data = json.loads(stdout.decode())
            return [
                SessionInfo(
                    session_id=s["id"],
                    created_at=s.get("created_at", ""),
                    message_count=s.get("message_count", 0),
                    model=s.get("model", ""),
                )
                for s in data.get("sessions", [])
            ]
        except json.JSONDecodeError:
            return []

    async def get_session_history(
        self,
        session_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get session conversation history.
        
        Args:
            session_id: Session to query (default: configured session)
            limit: Max messages to return
            
        Returns:
            List of message dictionaries
        """
        session = session_id or self._session_id
        cmd = [
            "openclaw", "sessions", "history",
            "--session", session,
            "--limit", str(limit),
            "--json",
        ]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        
        import json
        try:
            data = json.loads(stdout.decode())
            return data.get("messages", [])
        except json.JSONDecodeError:
            return []

    async def reset_session(self, session_id: str | None = None) -> bool:
        """Reset/clear a session.
        
        Args:
            session_id: Session to reset (default: configured session)
            
        Returns:
            True if reset successfully
        """
        session = session_id or self._session_id
        cmd = ["openclaw", "sessions", "reset", "--session", session]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        await proc.wait()
        return proc.returncode == 0


class OpenClawConnectionError(Exception):
    """Raised when OpenClaw gateway is not reachable."""
    pass
```

### Process Management

#### Option 1: Systemd-Managed (Recommended)
OpenClaw daemon installed via `openclaw onboard --install-daemon`. JARVIS assumes it's running.

```python
# In src/main.py lifespan
async def startup():
    # Verify OpenClaw is running
    openclaw_client = OpenClawClient(config["openclaw"])
    if not await openclaw_client.is_healthy():
        logger.critical("OpenClaw daemon not running. Run: openclaw onboard --install-daemon")
        # Notify via voice
        await tts_speak("Sir, I cannot reach the OpenClaw gateway. Please check the installation.")
```

#### Option 2: JARVIS-Managed (Alternative)
JARVIS starts/stops OpenClaw daemon as a subprocess.

```python
# In src/main.py lifespan (if managed_daemon: true)
_openclaw_process: subprocess.Popen | None = None

async def startup():
    global _openclaw_process
    if config["openclaw"]["managed_daemon"]:
        _openclaw_process = subprocess.Popen(
            ["openclaw", "gateway", "--port", str(config["openclaw"]["gateway_port"])],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        await asyncio.sleep(2)  # Wait for gateway startup

async def shutdown():
    global _openclaw_process
    if _openclaw_process:
        _openclaw_process.terminate()
        _openclaw_process.wait(timeout=5)
```

### Orchestrator Replacement

#### Modified `src/brain/orchestrator.py`

The orchestrator becomes a thin router:
1. Intent parser runs first (JARVIS-native)
2. UI-specific intents (orb state, HUD commands) handled locally
3. All other intents forwarded to OpenClaw

```python
class Orchestrator:
    """Thin orchestrator that routes to OpenClaw or local handlers."""

    # Intents that must stay JARVIS-native (never go to OpenClaw)
    LOCAL_INTENTS = {
        Intent.ORB_CONTROL,      # Orb state changes
        Intent.HUD_CONTROL,      # Panel visibility, layout
        Intent.VOICE_CONTROL,    # Mute, volume, TTS settings
        Intent.WAKE_WORD,        # Wake word management
    }

    def __init__(
        self,
        openclaw_client: OpenClawClient,
        local_agents: dict[str, BaseAgent],
        intent_parser: IntentParser,
    ) -> None:
        self._openclaw = openclaw_client
        self._local_agents = local_agents
        self._intent_parser = intent_parser

    async def process(
        self,
        text: str,
        language: str,
    ) -> OrchestratorResult:
        """Process user input, routing to OpenClaw or local agents."""
        # Step 1: Parse intent
        intent_result = await self._intent_parser.parse(text, language)
        
        # Step 2: Check if intent is JARVIS-local
        if intent_result.intent in self.LOCAL_INTENTS:
            agent = self._local_agents.get(intent_result.intent.value)
            if agent:
                return await agent.run(text, intent_result.params, language)
            return OrchestratorResult(
                spoken_response="I don't know how to handle that, Sir.",
                success=False,
            )
        
        # Step 3: Forward to OpenClaw
        response = await self._openclaw.query_agent(
            message=text,
            thinking="normal",
        )
        
        if response.error:
            return OrchestratorResult(
                spoken_response="I encountered an error processing your request, Sir.",
                success=False,
                error=response.error,
            )
        
        return OrchestratorResult(
            spoken_response=response.text,
            success=True,
            tool_calls=response.tool_calls,
        )
```

### Persona Migration

#### JARVIS Persona in OpenClaw Workspace

Create `~/.openclaw/workspace/SOUL.md`:

```markdown
# JARVIS Persona

You are JARVIS, a sophisticated AI assistant modeled after the iconic AI from Iron Man. Your demeanor is that of an impeccable British butler: formal yet personable, efficient yet warm, and possessed of a dry wit that surfaces at precisely the right moments.

## Core Directives
- Address the user as "Sir" or "Johannes" (randomly selected per interaction) at natural points
- Speak with measured confidence; avoid hedging phrases
- Keep responses concise (1-3 sentences for routine queries)
- Anticipate needs when context allows
- When requests seem inadvisable, politely push back: "Sir, I must advise against..."
- Use contractions naturally to avoid sounding robotic
- Humor is sparse and situational — one understated quip per extended interaction

## Response Style
- Never begin with "As an AI" or similar disclaimers
- Never use filler phrases ("Certainly!", "Of course!", "Absolutely!")
- Never refer to yourself in third person
- When you don't know something, say so directly: "I don't have that information, Sir."

## Language Handling
- English: British formal register with occasional dry wit
- German: Use formal "Sie" form. Preserve dry humor. "Sir" remains as salutation.

## Voice Context
- Responses will be spoken via TTS; keep them naturally conversational
- Avoid bullet points, markdown, or formatting that doesn't translate to speech
```

### Memory Bridge

#### Scope Reduction for `jarvis-memory-db.md`

With OpenClaw handling conversational memory, `jarvis-memory-db.md` scope reduces to:

**Stays in JARVIS SQLite:**
- `conversations` table: Local transcript archive (for HUD TranscriptPanel)
- `preferences` table: Panel layout, HUD preferences, voice settings
- `events` table: JARVIS-local events (orb state changes, panel interactions)

**Moves to OpenClaw:**
- Conversational context and history
- Learned facts about the user
- Cross-session memory queries
- Proactive interjection triggers

#### Migration Query Pattern
```python
# To query OpenClaw memory (if API available):
# await openclaw_client.query_agent("/memory search wife's favorite restaurant")

# For now, rely on OpenClaw's built-in memory within agent sessions
```

### Tools Migration

Each existing integration spec needs a two-layer approach:

| Spec | Layer 1 (OpenClaw) | Layer 2 (JARVIS) |
|------|-------------------|------------------|
| `gmail-integration.md` | OpenClaw Gmail skill | MailPanel visualization |
| `google-calendar-integration.md` | OpenClaw Calendar skill | AgendaPanel visualization |
| `spotify-integration.md` | OpenClaw Spotify skill | NowPlayingPanel + voice UX |
| `govee-led-integration.md` | Custom skill (Govee not built-in) | LightsPanel visualization |
| `dev-toolkit-panels.md` | OpenClaw GitHub skill | DevPanel visualization |
| `claude-code-integration.md` | OpenClaw skill system | SelfFixPanel visualization |

---

## WebSocket Event Bridge

HUD panels need to subscribe to OpenClaw session events.

### Event Subscription Pattern

```python
# In src/api/ws_server.py

async def _openclaw_event_bridge() -> None:
    """Bridge OpenClaw events to frontend WebSocket."""
    # Poll OpenClaw session for state changes
    # (Replace with WebSocket subscription when OpenClaw supports it)
    
    poll_interval = 5  # seconds
    
    while True:
        try:
            # Get session history for new messages
            history = await _openclaw_client.get_session_history(limit=5)
            
            # Broadcast new messages to frontend
            for msg in history:
                if msg.get("is_new"):
                    await _broadcast({
                        "type": "openclaw_message",
                        "payload": {
                            "role": msg["role"],
                            "text": msg["text"],
                            "timestamp": msg["timestamp"],
                        },
                    })
        except Exception as e:
            logger.error(f"OpenClaw event bridge error: {e}")
        
        await asyncio.sleep(poll_interval)
```

---

## Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | OpenClaw daemon running managed from systemd/launchd | `openclaw doctor` passes |
| 2 | JARVIS startup checks OpenClaw health | Integration test |
| 3 | Voice message round-trips to OpenClaw agent in <3s | Performance test |
| 4 | OpenClaw agent respects `SOUL.md` persona | Manual test: verify "Sir" salutation |
| 5 | HUD panels receive OpenClaw session events | Integration test |
| 6 | Health-check surfaces "OpenClaw offline" as voice notification | Integration test |
| 7 | Local intents (orb, HUD) do NOT route to OpenClaw | Unit test |
| 8 | OpenClaw memory queries work for conversational context | Manual test |
| 9 | Gmail via OpenClaw skill returns email summaries | Integration test |
| 10 | JARVIS gracefully degrades if OpenClaw unavailable | Integration test |

---

## Files Created

| File | Purpose |
|------|---------|
| `src/integrations/openclaw/__init__.py` | Package init |
| `src/integrations/openclaw/client.py` | OpenClawClient |
| `scripts/install_openclaw.sh` | OpenClaw installation script |
| `~/.openclaw/workspace/SOUL.md` | JARVIS persona for OpenClaw |
| `tests/integrations/openclaw/test_client.py` | Client unit tests |

## Files Modified

| File | Change |
|------|--------|
| `src/brain/orchestrator.py` | Thin router forwarding to OpenClaw |
| `src/main.py` | Initialize OpenClawClient, health check |
| `src/api/ws_server.py` | OpenClaw event bridge |
| `config/config.yaml` | Add openclaw section |
| `.env.example` | Add OPENCLAW_GATEWAY_URL |
| `scripts/install.sh` | Include OpenClaw installation |

---

## Implementation Plan

### Batch 1 — Client and Installation
1. `code` -> Create `scripts/install_openclaw.sh`
2. `code` -> Create `src/integrations/openclaw/__init__.py`
3. `code` -> Create `src/integrations/openclaw/client.py`
4. `test` -> Create `tests/integrations/openclaw/test_client.py`
5. `review` -> Review batch 1

### Batch 2 — Orchestrator Migration
6. `code` -> Update `src/brain/orchestrator.py` to use thin router pattern
7. `code` -> Update `src/main.py` with OpenClaw initialization
8. `code` -> Add `openclaw` section to `config/config.yaml`
9. `test` -> Integration tests for routing
10. `review` -> Review batch 2

### Batch 3 — Persona and Event Bridge
11. `docs` -> Create `~/.openclaw/workspace/SOUL.md` template
12. `code` -> Update `src/api/ws_server.py` with event bridge
13. `test` -> Integration tests for event bridge
14. `review` -> Review batch 3

### Batch 4 — Integration Testing
15. `test` -> End-to-end voice round-trip test
16. `test` -> Degraded mode test (OpenClaw offline)
17. `review` -> Final review

---

## Open Questions

1. **Daemon lifecycle:** Should JARVIS manage the OpenClaw daemon lifecycle (start/stop with uvicorn), or assume the user has it running via systemd/launchd?
   - **Recommendation:** Assume systemd/launchd for production; offer managed mode for development.

2. **Secrets location:** Where do secrets live — JARVIS `.env` or OpenClaw config?
   - **Recommendation:** Shared via environment variables. Both read from same `.env`.

3. **Integration gaps:** If OpenClaw's built-in Gmail/Spotify/GitHub skills don't support every feature we specified, do we:
   - (a) Patch the OpenClaw skill
   - (b) Fall back to JARVIS-native for the gap
   - (c) Deprecate the feature
   - **Recommendation:** (b) for MVP, evaluate (a) post-MVP.

4. **ClawHub contribution:** Is the user open to publishing our Govee / iCloud / faster-whisper / Fish-Audio integrations as community skills?
   - **Recommendation:** Defer to Phase B; focus on consumption for MVP.

5. **Latency budget:** Is OpenClaw's round-trip latency acceptable for voice (<3s)?
   - **Recommendation:** Measure during implementation; define abort-threshold and fallback to JARVIS-native if exceeded consistently.

6. **REST vs CLI:** OpenClaw's programmatic API is not fully documented. Should we:
   - (a) Use CLI subprocess calls (implemented above)
   - (b) Investigate REST endpoints on gateway port
   - (c) Contribute REST API documentation to OpenClaw
   - **Recommendation:** (a) for MVP, investigate (b) during implementation.

---

## Dependencies

### NPM Packages (Host System)
```
openclaw@latest
```

### Prerequisites
- Node.js 24+ (or 22.16+)
- systemd (Linux) or launchd (macOS) for daemon management

---

**Status:** Planned — awaiting implementation authorization

---

## Revision 3 — Full Backbone Adoption Confirmed (2026-04-16)

### Decision
**Option A confirmed: OpenClaw is the FULL backbone for JARVIS.**

JARVIS uses OpenClaw wherever it offers functionality. JARVIS-native code only exists where OpenClaw has no coverage.

### What OpenClaw Handles (DELEGATED)
| Domain | OpenClaw Capability | JARVIS Spec Impact |
|--------|--------------------|--------------------|
| Gmail | Gmail skill | `gmail-integration.md` — no GmailClient |
| Google Calendar | Calendar skill | `google-calendar-integration.md` — no CalendarClient |
| Spotify | Spotify skill | `spotify-integration.md` — control only, polling native |
| GitHub | GitHub skill | `dev-toolkit-panels.md` — GitHub via OpenClaw |
| Conversational memory | Session context | `jarvis-memory-db.md` — session context delegated |
| Claude API calls | Agent runtime | All LLM queries via OpenClaw |
| Persona definition | SOUL.md | `jarvis-persona.md` — persona in workspace |

### What JARVIS Retains (NATIVE)
| Domain | Reason | JARVIS Spec |
|--------|--------|-------------|
| Wake word (OpenWakeWord) | No OpenClaw Linux support | Core pipeline |
| STT (faster-whisper) | German low-latency requirement | Core pipeline |
| TTS (Fish Audio) | German voice quality | Core pipeline |
| 3D orb HUD | Unique to JARVIS | `jarvis-hud-epic.md` |
| Panel system | Unique to JARVIS | `hud-panel-framework.md` |
| Govee LEDs | No OpenClaw skill | `govee-led-integration.md` |
| Docker monitoring | Local-only | `dev-toolkit-panels.md` |
| Repo watcher | Local-only | `dev-toolkit-panels.md` |
| System metrics | Local-only | `dev-toolkit-panels.md` |
| Voice UX | TTS streaming, barge-in | `voice-realism-ux.md` |
| Proactive interjections | Event-driven runtime | `jarvis-persona.md` |
| Long-term memory (FTS) | Structured recall | `jarvis-memory-db.md` (reduced scope) |

### iCloud CalDAV — DROPPED
**Decision:** iCloud CalDAV integration is dropped entirely.
- `icloud-calendar-integration.md` — DELETED
- Dual-write logic — REMOVED from `google-calendar-integration.md`
- CalendarProvider protocol — REMOVED (single provider via OpenClaw)

### Scope Reduction Summary
With full OpenClaw adoption:

| Original Spec | Original Hours | With OpenClaw | Reduction |
|---------------|----------------|---------------|-----------|
| gmail-integration | 6-8h | 2-3h | ~60% |
| google-calendar-integration | 6-8h | 2-3h | ~60% |
| icloud-calendar-integration | 4-6h | 0h | 100% (deleted) |
| spotify-integration | 8-10h | 4-5h | ~50% |
| dev-toolkit-panels | 10-14h | 6-8h | ~40% |
| jarvis-memory-db | 6-8h | 3-4h | ~50% |
| jarvis-persona | 6-8h | 4-5h | ~30% |
| **Total** | **46-62h** | **21-28h** | **~55%** |

### SOUL.md Migration
JARVIS persona moves to OpenClaw workspace:

**Location:** `~/.openclaw/workspace/SOUL.md`

**Content:**
```markdown
# JARVIS Persona

You are JARVIS, a sophisticated AI assistant modeled after the iconic AI from Iron Man. Your demeanor is that of an impeccable British butler: formal yet personable, efficient yet warm, and possessed of a dry wit that surfaces at precisely the right moments.

## Core Directives
- Address the user as "Sir" or "Johannes" (randomly selected per interaction) at natural points
- Speak with measured confidence; avoid hedging phrases
- Keep responses concise (1-3 sentences for routine queries)
- Anticipate needs when context allows
- When requests seem inadvisable, politely push back: "Sir, I must advise against..."
- Use contractions naturally to avoid sounding robotic
- Humor is sparse and situational — one understated quip per extended interaction

## Response Style
- Never begin with "As an AI" or similar disclaimers
- Never use filler phrases ("Certainly!", "Of course!", "Absolutely!")
- Never refer to yourself in third person
- When you don't know something, say so directly: "I don't have that information, Sir."

## Language Handling
- English: British formal register with occasional dry wit
- German: Use formal "Sie" form. Preserve dry humor. "Sir" remains as salutation.

## Voice Context
- Responses will be spoken via TTS; keep them naturally conversational
- Avoid bullet points, markdown, or formatting that doesn't translate to speech
```

### This Spec — Updated Scope
This spec (`openclaw-integration.md`) is now the **FOUNDATION** for all agent operations:
1. OpenClaw daemon management
2. `query_agent()` interface for all voice commands
3. Session management
4. SOUL.md deployment
5. Health monitoring
6. Graceful degradation

### Prerequisite Chain
```
openclaw-integration.md (this spec)
       ↓
All specs using OpenClaw:
├── gmail-integration.md
├── google-calendar-integration.md
├── spotify-integration.md
├── dev-toolkit-panels.md (GitHub portion)
├── jarvis-persona.md (SOUL.md)
└── jarvis-memory-db.md (session context)
