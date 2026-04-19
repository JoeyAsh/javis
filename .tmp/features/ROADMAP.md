# JARVIS Roadmap — Stand 2026-04-19

Kurzüberblick für die nächste Session. Details und Akzeptanzkriterien stehen
jeweils in der benannten Einzel-Spec. Specs mit Status-Block oben drin
(`voice-realism-ux`, `jarvis-hud-epic`, `claude-code-integration`) haben eine
„umgesetzt / offen"-Aufschlüsselung direkt an der Quelle.

## Komplett fertig — Specs wurden gelöscht bzw. können gelöscht werden

- `openclaw-integration` — Voice-Pipeline routet durch OpenClaw-Gateway, `jarvis-main`-Session persistent, Health-Check per HTTP
- `jarvis-memory-db` — SQLite+FTS5-Archiv unter `data/jarvis.db`, jeder Transcript-Turn wird via `MemoryStore.record_event` abgelegt; Read-Path (Recall) noch nicht genutzt
- `jarvis-persona` — `SOUL.md` in OpenClaw-Workspace deployed, Sir/Johannes-Rotation, `ProactiveScheduler` + `EventBus`, `CAPABILITIES.md`
- `hud-panel-framework` — Floating-Window-Paradigma, Slot-Grid, Swap-Drag, Maximize, Win11-Snap, 3D-Tilt, Countdown-Ring
- `personal-assistant-epic` — Umbrella abgeschlossen: Gmail + Calendar live, Orchestrator injiziert Mail-/Kalender-Kontext pro Voice-Turn
- `gmail-integration` — Client (`src/integrations/google/gmail_client.py`), Backend-Poller in `ws_server.py`, MailPanel live via `subscribeMailStateStream`, Voice-Kontext über `_build_email_context`. Commit `746f13d` (2026-04-18)
- `google-calendar-integration` — Client (`src/integrations/google/calendar_client.py`), Backend-Poller, AgendaPanel live, Voice-Kontext über `_build_calendar_context`. Commit `c3b0c85` (2026-04-18)
- `spotify-integration` — Client (`src/integrations/spotify/client.py`), Poller + WS-Broadcast, NowPlaying-Panel live. Commit `746f13d` (2026-04-18)

## Teilweise fertig — Status-Block oben im jeweiligen Spec

- `voice-realism-ux` — **Fast komplett**: Streaming-TTS via persistenter Gateway-WS (`src/integrations/openclaw/ws_client.py`), Barge-In (`tts_pipeline.py:228`), Backchannels (`audio/backchannels.py`), Prosody (`audio/prosody.py`), Disfluencies (`audio/disfluency.py`) alle live. Commit `14830da` (2026-04-18). **Offen nur noch**: Feintuning & die kleineren Bugs unten (Sleep-Phrase-False-Positive, Zombie-Subprocess).
- `jarvis-hud-epic` — Agenda / Mail / NowPlaying / Dev (GitHub) jetzt live verdrahtet. Neu hinzugekommen: **LogPanel** (raw log stream + Turn-Timeline-Wasserfall). **Offen**: Lights-Panel (Govee fehlt backendseitig), SelfFix-Panel (noch Mock).
- `claude-code-integration` — LLM-Migration via OpenClaw erledigt. **Offen: Self-Debug-Loop.** Spec (49 kB) ist überholt — Empfehlung weiterhin: verwerfen und auf OpenClaw-Skills basierend neu schreiben falls Self-Debug gewünscht bleibt.

## Komplett offen

- `govee-led-integration` — kein Backend-Client vorhanden (`src/integrations/govee/` fehlt), LightsPanel nur Mock. Cloud-API + optional LAN.
- `dev-toolkit-panels` — GitHub-Panel live, Rest (Docker / Repo-Watcher / CI / SelfFix) noch nicht.

## Untracked — 2026-04-18/19 ausgeliefert, aber nie auf der Roadmap gewesen

- **JARVIS Controller** — Tauri-Desktop-App, paketiert als AppImage + `.deb`, unter `controller/src-tauri/`. Commit `328744c` (2026-04-19 10:50)
- **Google Drive Client** — `src/integrations/google/drive_client.py` (223 LOC), teilt OAuth-Fundament mit Gmail/Calendar. Commit `bda6675` (2026-04-18)
- **GitLab-Integration** — `src/integrations/gitlab/client.py` (410+ LOC): MRs, Issues, Pipelines in einem Batch via `fetch_state()`. Commit `bda6675`
- **Settings-Overlay + Push-to-Talk** im HUD. Commit `85cf5a8` (2026-04-18)
- **Systemd-User-Service** für Auto-Restart bei Crash. Commit `1be33ba` (2026-04-18)

## Offene Dev-Wünsche die kein eigenes Spec haben

1. **Sleep-Phrase False-Positive**: „Danke für die Info, kannst du noch…" triggert aktuell Closing. Fix: Sleep-Match nur wenn Utterance ≤ ~4 Tokens oder Phrase am Ende. ~10 LOC.
2. **Subprocess-Zombie beim STOP** — `asyncio.create_subprocess_exec` in `OpenClawClient.query_agent` kann 1-2 s verzögert beenden. Fix: expliziter `proc.kill()` bei Cancel. *(Hinweis: Relevanz prüfen, da Streaming-WS jetzt aktiv — der CLI-Fallback-Pfad ist evtl. gar nicht mehr der Hauptpfad.)*
3. **WS-Error-Console-Noise** — Browser-Console wirft `[ws] error Event` beim Backend-Restart bevor Reconnect greift. Kosmetisch, harmlos.
4. **Long-Term-Memory-Recall-Tool** — SQLite-FTS5 vorhanden, aber noch kein Chat-Agent-Tool, das es abfragt. „Erinner dich an Montag" funktioniert daher nicht über Sessions hinweg.

## Top-3 Empfehlung für die nächste Session

1. **Govee-LED-Integration** — letztes noch komplett offenes Integration-Panel; schließt das HUD-Epic auf Lights-Seite ab. Cloud-API-Client + Poller analog zu Spotify.
2. **Sleep-Phrase-Fix + Zombie-Cleanup** — 20 LOC Gesamtaufwand, spürbare UX-Verbesserung, reduziert Frust im Alltagsbetrieb.
3. **Long-Term-Memory-Recall-Tool** — macht die bereits vorhandene `events`-Tabelle endlich nutzbar; kleines, isoliertes Feature mit großem gefühltem Nutzen („JARVIS, worum ging es gestern Abend?").
