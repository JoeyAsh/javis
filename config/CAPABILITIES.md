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

<!-- snapshot as of 2026-04-19 -->

---

## Voice pipeline

- **Wake word**: OpenWakeWord with the `hey_jarvis` / `alexa` default
  models. Threshold 0.3, VAD 0.5. Runs on the live browser-mic audio
  stream as raw Int16 PCM at 16 kHz mono.
- **Speech-to-text (STT)**: `faster-whisper` `small` model, int8 on
  CPU. Pinned to German (`language: "de"`) by default — set to
  `"auto"` in `config/config.yaml` for open-ended auto-detect.
- **LLM**: routes all conversational turns through the local
  **OpenClaw gateway** via a **persistent WebSocket** (streaming) at
  `ws://127.0.0.1:18789`. Agent model: `claude-cli/claude-opus-4-7`.
  Session id: `jarvis-main` (the gateway owns short-term conversational
  memory per session). Thinking level configurable (`off | minimal |
  low | medium | high | xhigh`) — currently `medium`.
- **Text-to-speech (TTS)**: Fish Audio cloud (`api.fish.audio/v1/tts`),
  MP3 output streamed to the frontend as base64 via the `audio` WS
  message. Uses the cloned JARVIS voice profile configured via
  `FISH_VOICE_ID`. **Streaming TTS** is live — partial LLM tokens are
  synthesised and played as soon as sentence boundaries arrive.
- **Barge-in**: live — TTS playback is cancelled immediately on a new
  wake-word / voice event (`src/audio/tts_pipeline.py`).
- **Backchannels & prosody**: live — short acknowledgements (`mhm`,
  `ja`, `ok`) via `src/audio/backchannels.py`; prosody hints (speed
  0.8–1.2, energy levels) via `src/audio/prosody.py`; mild
  disfluencies via `src/audio/disfluency.py`.
- **Conversation mode**: after every successful voice turn the mic
  stays open for an **18 s follow-up window** so the user can keep
  talking without saying the wake word again. Natural sleep phrases
  — `danke`, `das war's`, `tschüss`, `thanks`, `bye`, ... — close
  the session with a warm closing line (`Gern, {sal}.` / `Anytime,
  {sal}.`) instead of routing through the LLM.
- **Quick-ack filler audio**: within ~300 ms of STT finishing, one of
  eight pre-cached filler MP3s (DE: *Moment*, *Einen Augenblick*,
  *Gleich*, *Klar*; EN: *Just a moment*, *One second*, *Right*,
  *Certainly*) is broadcast to mask remaining round-trip latency.
- **Push-to-Talk**: available in the HUD as alternative to wake word.

## Memory

- **Short-term**: owned by **OpenClaw**, scoped to the gateway
  session id (`jarvis-main` for voice turns). Every LLM turn has
  full awareness of the prior conversation within that session.
- **Long-term archive**: local SQLite + FTS5 at `data/jarvis.db`.
  The `events` table stores every transcript turn (`user` + `jarvis`)
  and every proactive notification with timestamps. Append-only — the
  read path (voice-driven recall, e.g. "erinner dich an letzte
  Woche") is **planned but not yet wired** as an agent tool.
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
  - **Mail (Inbox)**: live via Gmail poller + `subscribeMailStateStream`.
  - **Agenda**: live via Google Calendar poller.
  - **NowPlaying**: live via Spotify poller.
  - **Dev-Toolkit (GitHub)**: live via GitHub poller (`useGitHubState`).
  - **LogPanel**: raw backend log stream + turn-timeline waterfall
    (latency per turn, per stage).
- **Mock panels** (data not yet sourced from live integrations):
  Lights (Govee), SelfFix.
- **Orb** (Three.js): per-state visual — idle / listening / thinking
  / speaking. `follow_up` state with a muted pulse + a 5 s countdown
  ring during the last five seconds of the follow-up window.
- **Settings overlay**: in-HUD configuration panel.

## Integrations

- **Gmail**: live. Full client (`src/integrations/google/gmail_client.py`),
  backend poller, MailPanel wired, Orchestrator injects mail context
  per voice turn (`_build_email_context`).
- **Google Calendar**: live. Client
  (`src/integrations/google/calendar_client.py`), poller, AgendaPanel
  wired, Orchestrator injects calendar context per voice turn
  (`_build_calendar_context`), proactive 10-min meeting reminder.
- **Google Drive**: live. Client
  (`src/integrations/google/drive_client.py`), shares OAuth foundation
  with Gmail/Calendar.
- **Spotify**: live. Client (`src/integrations/spotify/client.py`),
  poller + WS broadcast, NowPlaying panel. Requires Spotify Premium
  for playback controls.
- **GitHub**: live. Poller + Dev-Toolkit panel.
- **GitLab**: live. Client (`src/integrations/gitlab/client.py`) —
  MRs, issues, pipelines batched via `fetch_state()`.
- **WhatsApp**: via OpenClaw channel (`channels.whatsapp.enabled =
  true`). Outbound messaging only on explicit user request, to
  whitelisted numbers.
- **Govee LEDs**: **not yet wired** — no backend client, Lights panel
  still mock.

## Active OpenClaw config

Snapshot of `~/.openclaw/openclaw.json`:

- `gateway.mode` = `local` — required; otherwise the daemon exits
  with code 78 at startup.
- `gateway.auth.mode` = `token` (token in the config file).
- `agents.defaults.model` = `claude-cli/claude-opus-4-7`.
- `agents.defaults.memorySearch.enabled` = `false`.
- `channels.whatsapp.enabled` = `true` (in active use by JARVIS for
  outbound messages on explicit request).
- `plugins.entries.anthropic.enabled` = `true`.

## Packaging & runtime

- **JARVIS Controller**: Tauri desktop app under `controller/src-tauri/`,
  packaged as AppImage and `.deb`.
- **Systemd user service** for auto-restart on crash.

## Known limitations

- **Govee LEDs not yet wired** — cannot control lighting scenes.
- **Self-Debug-Loop not implemented** — SelfFix panel is mock; no
  autonomous code-repair loop.
- **Long-term recall over SQLite not queryable from voice** — archive
  is written, but no chat-agent tool reads it back. Recall across
  older OpenClaw sessions therefore still does not work end-to-end.
- **No direct SMS / phone** — outbound voice/SMS is not wired
  (WhatsApp is).
- **Sleep-phrase false-positives** — e.g. "Danke für die Info,
  kannst du noch…" can still trigger closing on occasion (fix
  planned).

## Roadmap (short)

1. **Govee LED integration** — close the last remaining mock panel
   (Lights) with a cloud-API client; optional LAN fallback.
2. **UX polish**: sleep-phrase false-positive fix (~10 LOC), explicit
   subprocess kill on STOP, suppress WS-error console noise on
   backend restart.
3. **Long-term memory recall tool** — chat-agent tool that queries
   the SQLite `events` table (FTS5), so "erinner dich an Montag"
   works reliably across OpenClaw sessions.
4. **Self-Debug-Loop** — re-scope the old `claude-code-integration`
   spec on top of OpenClaw skills if the autonomous self-fix loop is
   still desired.
5. **Dev-Toolkit extensions** — Docker / Repo-Watcher / CI panels
   beyond the existing GitHub+GitLab.

---

*This file lives at `config/CAPABILITIES.md` in the JARVIS repo and is
deployed to `~/.openclaw/workspace/CAPABILITIES.md` during
`scripts/install_openclaw.sh`.*
