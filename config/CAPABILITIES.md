# JARVIS Capability Inventory

> **Instruction for the agent:** If the user asks what you can do, what
> is configured, or what is next — cite this file precisely. Do **not**
> hallucinate capabilities that are listed below as planned or absent.
> State clearly when something is not yet wired.
>
> **Hinweis für den Agenten:** Wenn der Nutzer fragt, was du kannst, was
> konfiguriert ist, oder was als Nächstes ansteht — zitiere diese Datei
> präzise. Erfinde **keine** Fähigkeiten, die hier als geplant oder
> noch nicht verfügbar gelistet sind. Wenn etwas fehlt, sag das klar.

<!-- snapshot as of 2026-04-17 -->

---

## Voice pipeline

- **Wake word**: OpenWakeWord with the `hey_jarvis` / `alexa` default
  models. Threshold 0.3, VAD 0.5. Runs on the live browser-mic audio
  stream as raw Int16 PCM at 16 kHz mono.
- **Speech-to-text (STT)**: `faster-whisper` `small` model, int8 on
  CPU. Pinned to German (`language: "de"`) by default — set to
  `"auto"` in `config/config.yaml` for open-ended auto-detect.
- **LLM**: routes all conversational turns through the local
  **OpenClaw gateway** (JSON-RPC-style HTTP at `http://127.0.0.1:18789`).
  Agent model: `claude-cli/claude-opus-4-7`. Session id: `jarvis-main`
  (the gateway owns short-term conversational memory per session).
  Thinking level configurable (`off | minimal | low | medium | high
  | xhigh`) — currently `medium`.
- **Text-to-speech (TTS)**: Fish Audio cloud (`api.fish.audio/v1/tts`),
  MP3 output streamed to the frontend as base64 via the `audio` WS
  message. Uses the cloned JARVIS voice profile configured via
  `FISH_VOICE_ID`.
- **Conversation mode** *(new)*: after every successful voice turn
  the mic stays open for an **18 s follow-up window** so the user
  can keep talking without saying the wake word again. Natural sleep
  phrases — `danke`, `das war's`, `tschüss`, `thanks`, `bye`, ... —
  close the session with a warm closing line (`Gern, {sal}.` /
  `Anytime, {sal}.`) instead of routing through the LLM.
- **Quick-ack filler audio** *(new)*: within ~300 ms of STT finishing,
  one of eight pre-cached filler MP3s (DE: *Moment*, *Einen
  Augenblick*, *Gleich*, *Klar*; EN: *Just a moment*, *One second*,
  *Right*, *Certainly*) is broadcast to mask the 7–11 s OpenClaw
  round-trip. The real response follows on the existing audio queue.

## Memory

- **Short-term**: owned by **OpenClaw**, scoped to the gateway
  session id (`jarvis-main` for voice turns). Every LLM turn has
  full awareness of the prior conversation within that session; ask
  "what did I just say?" and I can answer.
- **Long-term archive**: local SQLite at `data/jarvis.db`. The
  `events` table stores every transcript turn (`user` + `jarvis`)
  and every proactive notification with timestamps. This is
  append-only — the read path (voice-driven recall, e.g. "erinner
  dich an letzte Woche") is **planned but not yet wired** into the
  orchestrator.
- **Memory search**: OpenClaw's semantic memory search
  (`agents.defaults.memorySearch.enabled`) is **disabled** — needs an
  embedding provider we haven't configured.

## HUD (browser frontend)

- **Floating-window slot grid**: 3 × N slots, drag to reorder, swap
  on drop, double-click a window's title bar to maximise into a
  10-column layout (one panel full width, dev-toolkit split below),
  double-click again to snap back.
- **Live panels wired to the backend**:
  - **System**: CPU / RAM / GPU / CPU-temp / net / disk from psutil +
    GPUtil, refreshed every 2 s over a dedicated WS stream.
  - **Transcript**: each `transcript` WS frame appends a turn.
  - **Notifications**: fed by the `ProactiveScheduler` — meeting
    reminder (10 min advance), dirty-repo idle (2 h), system alerts
    (CPU ≥ 85 % / RAM ≥ 90 % / disk ≥ 95 %), VIP-mail, late-night.
  - **TopBar**: live clock + date + Open-Meteo weather for the
    configured location.
- **Mock panels** (data not yet sourced from live integrations):
  Agenda, Inbox, NowPlaying, Lights, Dev-Toolkit, SelfFix.
- **Orb** (Three.js): per-state visual — idle / listening / thinking
  / speaking. **New** `follow_up` state with a muted pulse + a 5 s
  countdown ring during the last five seconds of the follow-up
  window.

## Active OpenClaw config

Snapshot of `~/.openclaw/openclaw.json`:

- `gateway.mode` = `local` — required; otherwise the daemon exits
  with code 78 at startup.
- `gateway.auth.mode` = `token` (token in the config file).
- `agents.defaults.model` = `claude-cli/claude-opus-4-7`.
- `agents.defaults.memorySearch.enabled` = `false`.
- `channels.whatsapp.enabled` = `true` (channel registered, not yet
  used by JARVIS).
- `plugins.entries.anthropic.enabled` = `true`.

## Known limitations

- **No streaming LLM yet** — the OpenClaw CLI is one-shot
  request/response. Each voice turn therefore pays the full 7–11 s
  latency; the quick-ack filler above masks it audibly, but the
  real audio does not arrive sooner.
- **Gmail, Google Calendar, Spotify, Govee LEDs** — panels exist in
  the HUD, spec-files are planned under `.tmp/features/`, but the
  integrations are **not yet wired**. I cannot read mail, add
  calendar events, control music, or control lights.
- **No direct WhatsApp / SMS / phone** — no outbound messaging.
- **Cannot recall sessions older than the current OpenClaw session**
  via the LLM side — the SQLite archive exists but is not yet
  queried by the chat agent.

## Roadmap (short)

1. **Gmail** skill via OpenClaw — list inbox, search by sender,
   read message, flag VIPs. Wired to the live Inbox panel.
2. **Google Calendar** skill — upcoming events, conflict detection,
   proactive 10-minute reminder currently only stubbed.
3. **Long-term memory recall** — chat agent tool that queries the
   SQLite `events` table, so "erinner dich an Montag" works
   reliably across OpenClaw sessions.
4. **Streaming via gateway WebSocket** — replace the one-shot CLI
   path with OpenClaw's streaming protocol to cut the ~3.7 s CLI
   startup tax.
5. **Spotify** (now-playing + shuffle/next/prev voice controls).
6. **Govee LEDs** via cloud API — lighting scenes on voice.

---

*This file lives at `config/CAPABILITIES.md` in the JARVIS repo and is
deployed to `~/.openclaw/workspace/CAPABILITIES.md` during
`scripts/install_openclaw.sh`.*
