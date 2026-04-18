# JARVIS Roadmap — Stand 2026-04-17

Kurzüberblick für die nächste Session. Details und Akzeptanzkriterien stehen
jeweils in der benannten Einzel-Spec. Specs mit Status-Block oben drin
(`voice-realism-ux`, `jarvis-hud-epic`, `claude-code-integration`) haben eine
„umgesetzt / offen"-Aufschlüsselung direkt an der Quelle.

## Komplett fertig — Specs wurden gelöscht

- `openclaw-integration` — Voice-Pipeline routet durch OpenClaw-Gateway, `jarvis-main`-Session persistent, Health-Check per HTTP
- `jarvis-memory-db` — SQLite+FTS5-Archiv unter `data/jarvis.db`, jeder Transcript-Turn wird via `MemoryStore.record_event` abgelegt; Read-Path (Recall) noch nicht genutzt
- `jarvis-persona` — `SOUL.md` in OpenClaw-Workspace deployed, Sir/Johannes-Rotation, `ProactiveScheduler` + `EventBus`, `CAPABILITIES.md`
- `hud-panel-framework` — Floating-Window-Paradigma, Slot-Grid, Swap-Drag, Maximize, Win11-Snap, 3D-Tilt, Countdown-Ring

## Teilweise fertig — Status-Block oben im jeweiligen Spec

- `voice-realism-ux` — Conversation-Mode, Sleep-Phrases, Quick-Ack-Filler, Single-Call-Pipeline, STOP-Button laufen. **Offen: Streaming, Barge-In, Backchannels, Prosody.** Größter perceived-latency-Gewinn liegt beim Streaming via persistenter WS-Verbindung zum Gateway.
- `jarvis-hud-epic` — Framework + SystemPanel + TranscriptPanel + NotificationsPanel sind live verdrahtet. **Offen: Agenda / Mail / NowPlaying / Lights / Dev / SelfFix — alle noch auf Mock. Jedes Panel hat eine eigene Integration-Spec (siehe unten).**
- `claude-code-integration` — Der LLM-Migrations-Teil ist durch OpenClaw erledigt. **Offen: der gesamte Self-Debug-Loop.** Spec ist 49 kB, weitgehend überholt — Empfehlung: verwerfen und auf OpenClaw-Skills basierend neu schreiben wenn Self-Debug gewünscht bleibt.

## Komplett offen — Specs unverändert, warten auf Umsetzung

- `personal-assistant-epic` — Umbrella für Gmail + Calendar. Empfehlung: durch OpenClaw-Skills statt custom Python-Clients. Gmail-MCP-Tools sind in der Anthropic-Session bereits verfügbar.
- `gmail-integration` — Voice-Routing + Mail-Panel live wiring. Höchster User-Value als nächster Schritt.
- `google-calendar-integration` — Voice + Agenda-Panel live wiring. Plus Trigger für ProactiveScheduler („Meeting in 10 Min").
- `spotify-integration` — NowPlaying-Panel live wiring. Setzt Spotify Premium voraus.
- `govee-led-integration` — Lights-Panel. Cloud-API + optional LAN.
- `dev-toolkit-panels` — GitHub/Docker/Repo-Watcher/CI/System-Monitor. SystemMonitor ist schon live, Rest noch nicht.

## Offene Dev-Wünsche die kein eigenes Spec haben

1. **Streaming-TTS via persistenter Gateway-WS-Verbindung** — größter Hebel für „fühlt sich menschlich an". Aktuell geht jeder Turn als eigener Node-Subprocess → ~3.7 s Startup-Overhead + keine Streaming-Antwort. Lösung: WebSocket direkt zum Gateway (`ws://127.0.0.1:18789`), Protokoll rausreverse-engineeren, persistent halten. Ist als „Phase 4" markiert, deferred.
2. **Sleep-Phrase False-Positive**: „Danke für die Info, kannst du noch…" triggert aktuell Closing. Fix: Sleep-Match nur wenn Utterance ≤ ~4 Tokens oder Phrase am Ende. ~10 LOC.
3. **Console/Log-Panel im HUD** — User-Wunsch: Backend-Log + optional OpenClaw-Log live im HUD. Zwei Flavors skizziert: raw-log-stream vs. turn-timeline (Wasserfall-Diagramm der Latenzen pro Turn). Details in der Diskussion vom 2026-04-17.
4. **Subprocess-Zombie beim STOP** — `asyncio.create_subprocess_exec` in `OpenClawClient.query_agent` kann 1-2 s verzögert beenden. Fix: expliziter `proc.kill()` bei Cancel.
5. **WS-Error-Console-Noise** — Browser Console wirft `[ws] error Event` beim Backend-Restart bevor Reconnect greift. Kosmetisch, eigentlich harmlos.

## Top-3 Empfehlung für die nächste Session

1. **Gmail-Integration** — größter User-Value, MCP-Tools sind schon in der Session, kurzer Weg zum ersten echten Personal-Assistant-Feature
2. **Streaming via Gateway-WS** — löst die „fühlt sich langsam an"-Kernbeschwerde strukturell
3. **Google-Calendar + Proactive-Trigger** — direkter Next-Step nach Gmail, aktiviert endlich die Meeting-Reminder-Logik die bereits im ProactiveScheduler steht
