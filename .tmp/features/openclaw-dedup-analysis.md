# OpenClaw Dedup — was kann aus JARVIS raus

**Stand 2026-04-18. Quelle: `/home/paps/Repos/openclaw` (main branch, 53 built-in skills + 113 extensions).**

JARVIS hat an mehreren Stellen Infrastruktur nachgebaut, die OpenClaw bereits
ab Werk liefert. Unten eine nüchterne Liste, sortiert nach **Aufräum-Potenzial**
(1 = sicher löschen / stark verschlanken, 2 = Teil-Ersatz möglich, 3 = behalten,
weil JARVIS-spezifisch oder OpenClaw liefert's nicht).

## Harte Randbedingungen (bleiben unangetastet)

- **Frontend** (`frontend/`) — dein eigenes HUD. OpenClaw hat nur einen
  minimalen WebChat, das ersetzt unsere Orb/Panel-UX nicht.
- **Fish Audio TTS** (`src/audio/fish_tts.py`) — deine Jarvis-Stimme. OpenClaw
  hat zwar `speech-core` + `sherpa-onnx-tts`/`deepgram`, aber keine
  Fish-Audio-Anbindung und klingt nicht nach Jarvis.
- **Wake Word** (`src/audio/wake_word.py`) — OpenWakeWord läuft lokal, kein
  Äquivalent in OpenClaw.

---

## Tier 1 — sicher rausnehmen bzw. stark verschlanken

### 1.1 `src/brain/memory/` (SQLite-Event-Archiv)

**Aktuell:** FTS5-Event-Log unter `data/jarvis.db` (Schema, store, backup).
~500 LOC.

**OpenClaw liefert:** `memory-core` (built-in). SQLite + FTS5 + optional
Vector-Search via Embedding-Provider. Siehe
`docs/concepts/memory-builtin.md`. Dazu Markdown-Workspace-Memory (MEMORY.md +
`memory/YYYY-MM-DD.md`) und Tools `memory_search`, `memory_get`.

**Empfehlung:**
- Kompletter Ausbau: alle `MemoryStore`-Aufrufe in `ws_server.py` und
  `orchestrator.py` entfernen. OpenClaw schreibt die Session-History bereits
  selbst (`jarvis-main`-Session). Keine doppelte Archivierung nötig.
- **Falls lokales Backup gewünscht** (Airplane-Mode-Szenario): Minimal-Version
  beibehalten (nur `record_event` als Append-Only-File-Writer, ~30 LOC). Aber
  `brain/memory/backup.py`, `brain/memory/schema.py`, Index und CLI können
  alle weg.
- **Gewinn:** ~500 LOC raus, eine SQLite-Abhängigkeit weniger, keine Sorgen
  um Schema-Migrationen und Backup-Timer.

### 1.2 `src/brain/proactive.py` + `src/utils/events.py` (ProactiveScheduler + EventBus)

**Aktuell:** eigener Scheduler für Calendar-Reminder, VIP-Mail, Dirty-Repo,
System-Alerts, VIP-Rotation. EventBus für Pub/Sub. ~400 LOC.

**OpenClaw liefert:**
- **Cron-Jobs** direkt im Gateway (`docs/concepts/architecture.md` → Events:
  `cron`). Definierbar in `~/.openclaw/openclaw.json` oder per Skill.
- **Heartbeat**-Events als natürliche Ticks.
- **Sessions für Cron** — jede Cron-Ausführung bekommt frische Session, Agent
  kann dort tooling + Memory voll nutzen.

**Empfehlung:**
- Calendar-/Mail-Reminder als OpenClaw-Cron-Job neu schreiben, der unseren
  bestehenden Gmail-/Calendar-Client aufruft und via WS eine HUD-Notification
  pusht. ProactiveScheduler dann löschen.
- EventBus weg — OpenClaw-Events laufen direkt auf dem Gateway-WS.
- **Gewinn:** ~400 LOC raus, ein Timing-Loop weniger, Scheduler-Konfig
  deklarativ statt im Python-Code.

### 1.3 `src/brain/salutation.py` + `src/brain/conversation_mode.py` (Persona-Teile)

**Aktuell:** Sir/Johannes-Rotation, Sleep-Phrases + Closing, Follow-Up-Window.
~200 LOC.

**OpenClaw liefert:**
- **SOUL.md** (`docs/concepts/soul.md`) injiziert Persona + Anrede in jede
  Session. Johannes/Sir-Rotation + Tonalität gehören dort hin, nicht in
  Python-Code.
- **Session-Management** (`docs/concepts/session.md`) — Session-Lifecycle ist
  Gateway-Job.

**Empfehlung:**
- Salutation-Config nach `~/.openclaw/workspace/SOUL.md` migrieren (teils
  schon getan). `salutation.py` komplett weg.
- Follow-Up-Window ist JARVIS-spezifische Audio-UX — **behalten**, aber die
  „Session-ist-vorbei"-Semantik sollte ein OpenClaw-Session-Close-Event sein,
  kein lokaler Timer. `conversation_mode.py` schrumpft auf reine
  Sleep-Phrase-Detektion (~50 LOC).
- **Gewinn:** ~150 LOC raus.

### 1.4 `src/brain/response_cache.py` + `src/brain/response_length.py`

**Aktuell:** lokale Caches + Längen-Heuristiken.

**OpenClaw liefert:** Block-Streaming + Chunking-Engine
(`docs/concepts/streaming.md`) — `EmbeddedBlockChunker` mit min/max-Chars,
Break-Preference, Coalescing. Deckt unsere Längen-Logik vollständig ab.

**Empfehlung:** beide Module löschen. Block-Streaming im
Gateway-Config konfigurieren (`agents.defaults.blockStreamingChunk`). Unser
`StreamSplitter` in `src/audio/stream_splitter.py` bleibt, weil er
Satz-Grenzen für **TTS-Pipelining** erkennt — das ist eine andere
Aufgabe.

### 1.5 `src/integrations/github/` (komplett)

**Aktuell:** 500 LOC eigener REST-Client (`client.py` + `poller.py`) + 36
Tests. Nutzt `/search/issues` — hat uns gerade einen Rate-Limit-Stau
beschert (Search-API hat nur 30 Req/h, nicht die 5000 des Core-API).

**OpenClaw liefert:** built-in **`github`**-Skill (`openclaw/skills/github/`).
Wrapper um `gh` CLI. Deckt ab: PR-Status, CI-Runs, Issues
(list/create/comment), Code-Review, generische API-Queries. Auth via
`gh auth login` (interaktiv, robuster als PAT-in-`.env`).

Dazu **`gh-issues`** — feuert Sub-Agents ab, die Issues fixen + PRs öffnen.
Das haben wir nie gebaut.

**Trade-off:**
- Unser HUD-DevPanel-Poller broadcastet alle 60 s Live-State. Das
  `github`-Skill macht das nicht — Skills werden vom LLM via Tool-Use
  gerufen.
- Zwei saubere Wege zur Ablösung:
  1. **On-demand**: DevPanel zeigt kein Live-Polling mehr, stattdessen
     triggert eine Voice-Frage („was sind meine offenen PRs?") das
     `github`-Skill, und JARVIS pusht die Antwort einmal ins Panel.
  2. **Cron-gescheduled**: OpenClaw-Cron-Job ruft das `github`-Skill
     alle 60 s, Resultat geht via Gateway-Event ins HUD. Das ist dann
     dasselbe Verhalten wie heute, aber ohne unseren Python-Code.

**Empfehlung:** Weg 2 (Cron + Skill). Komplettes `src/integrations/github/`
löschen. Voraussetzung: `gh` installiert und `gh auth login` einmal
durchlaufen. `GITHUB_TOKEN` in `.env` wird dadurch überflüssig.

**Gewinn:** ~500 LOC raus, 36 Tests raus, Rate-Limit-Bug gratis weg
(weil `gh` CLI über die Core-API geht, nicht die Search-API).

---

## Tier 2 — Teil-Ersatz möglich, Entscheidung nötig

### 2.1 Lokale Intent-Agents (`src/brain/agents/` + `src/brain/intent_parser.py`)

**Aktuell:** Regex-basierter Intent-Parser klassifiziert `PC_CONTROL`,
`SMART_HOME`, `SYSTEM`, plus EMAIL_* / CALENDAR_* / DRIVE_* / SPOTIFY_* /
GITHUB_* intents. PcAgent / SmartHomeAgent / SystemAgent dispatched lokal.

**OpenClaw liefert:**
- **Skills-System** (`docs/concepts/agent.md` → „Skills"). Lädt Skills aus
  `<workspace>/skills/` oder Bundle-Skills. Der Agent selbst ruft das
  passende Skill via Tool-Use auf — **kein Regex-Parser nötig**.
- Von Haus aus: `github`, `gh-issues`, `spotify-player`, `notion`, `weather`,
  `openai-whisper`, `voice-call`, `slack`, `apple-notes`, `apple-reminders`,
  `session-logs`, `summarize`, und viele mehr (siehe `openclaw/skills/`).

**Trade-off:**
- **Delegieren an OpenClaw-Skill** → kein `intent_parser.py` mehr nötig,
  LLM entscheidet via Tool-Use welches Skill läuft. Vorteil: flexibler,
  Kontext-sensitiver. Nachteil: jeder Turn kostet einen LLM-Roundtrip
  (keine `skip_orchestrator_on_clear_intent`-Abkürzung mehr).
- **Lokale Fast-Path behalten** → unser aktueller Pfad liefert ~100 ms
  Response für hochkonfidente Intents ohne LLM-Round-Trip. Das geht mit
  Skills nicht.

**Empfehlung:**
- **PcAgent, SmartHomeAgent, SystemAgent** → behalten als Fast-Path (brauchen
  Latenz-vorteil für „Licht an", „neustart", System-Metriken).
- **EMAIL/CALENDAR/DRIVE Intents** → behalten als Fast-Path, weil sie Gmail-/
  Calendar-Client direkt ohne LLM ansteuern (~2 s statt ~8 s).
- **GITHUB-Intents** → siehe Tier 1.5 (GitHub komplett an `github`-Skill
  delegieren, inkl. Poller via OpenClaw-Cron).
- **SPOTIFY-Intents** → können weg, wenn wir stattdessen das OpenClaw
  `spotify-player`-Skill nutzen. ABER: dann fällt das live-polling fürs
  NowPlayingPanel weg. Also besser **Spotify-Poller behalten** (Web-API
  für HUD-State) und **Voice-Intent entfernen** (Voice delegiert an
  OpenClaw-Skill).
- **Gewinn:** ~100 LOC raus (Spotify-Intent-Handling; GitHub-Intent wird
  Teil des ganzen GitHub-Ausbaus aus Tier 1.5).

### 2.2 STT (`src/audio/stt.py`, faster-whisper)

**Aktuell:** lokales Whisper-Small, ~6-7 GB RAM, 300 ms Latenz.

**OpenClaw liefert:**
- `deepgram` extension (Cloud-STT, ~200 ms via Nova-3)
- `openai-whisper` + `openai-whisper-api` skills (Cloud)

**Trade-off:**
- Cloud-STT hat geringere Latenz (200 ms vs 300 ms), aber sendet Audio an
  Deepgram/OpenAI → Privacy-Hit.
- Lokales Whisper ist offline-fähig.

**Empfehlung:** **behalten**. Whisper-small ist kostenlos, offline, und „gut
genug". Nur relevant falls wir auf sehr leistungsschwache Hardware (Raspberry
Pi) deployen — dann wäre Cloud-STT eine Notlösung.

### 2.3 Streaming-LLM-Client (`src/integrations/openclaw/ws_client.py`)

**Aktuell:** 726 LOC persistent WS client mit Ed25519-Handshake, Auto-Reconnect,
Per-Run-Queue, Cumulative-to-Incremental-Conversion, Stall-Timeout.

**OpenClaw liefert:** denselben WS-Protokoll (`docs/gateway/protocol.md`) —
aber die Code-Implementation dafür haben wir selbst geschrieben, weil es noch
keine offizielle Python-SDK gibt. Siehe `packages/` — nur `memory-host-sdk`,
`plugin-sdk`, `plugin-package-contract`. **Keine Python-Client-SDK.**

**Empfehlung:** **behalten**. Solange OpenClaw keine Python-SDK released,
bleibt unser Client der Weg. Sobald eine offizielle Python-SDK kommt →
migrieren und ~600 LOC sparen.

---

## Tier 3 — behalten (JARVIS-spezifisch oder OpenClaw liefert's nicht)

### 3.1 Gmail / Calendar / Drive (`src/integrations/google/`)

OpenClaw hat KEINE Google-Workspace-Integration als Skill oder Extension. Die
`google` Extension ist nur der Gemini-LLM-Provider. Unsere Clients (Gmail v1
API, Calendar v3, Drive v3) sind einzigartig und bleiben. Evtl. später als
OpenClaw-Skill re-packen und upstream beitragen.

### 3.2 GitLab (`src/integrations/gitlab/`)

OpenClaw hat **kein** eingebautes GitLab-Skill (nur ClawHub-Community-Skills wie `gitlab-cli-skills`). Eigenen Client **komplett behalten** — oder später durch `gitlab-cli-skills` ersetzen, falls du die `glab` CLI installierst.

### 3.3 Govee / Home Assistant / Fish Audio / Voice-Pipeline-UX

- **Govee**: nicht implementiert, nicht in OpenClaw → egal.
- **Home Assistant**: OpenClaw hat `smart-home`-ähnliche Hooks nicht;
  unser Code (im Moment deaktiviert) bleibt als Zukunft.
- **Fish Audio TTS**: behalten, siehe oben.
- **Quick-Ack / Backchannels / Disfluencies / Prosody / Sleep-Phrase-Matcher**:
  alles JARVIS-Audio-UX. OpenClaw hat TTS-Provider aber keine dieser
  Interaktions-Polish-Layer.

### 3.4 HUD-Poller (`_start_*_poller` in ws_server.py)

Mail-, Calendar-, GitLab-, Spotify-Poller broadcasten State an unser HUD.
OpenClaw hat keine „State-Poller → Frontend" Infrastruktur.
Behalten. Nur die **Intent-Dispatcher** davon sind redundant (siehe 2.1).

**Ausnahme GitHub-Poller:** ersatzlos löschen, weil ein OpenClaw-Cron-Job
das `github`-Skill alle 60 s aufruft und das Resultat direkt ins HUD
pusht (siehe Tier 1.5). `_start_github_poller` geht komplett weg,
`broadcast_github_state` kann zu einem dünnen Adapter werden, der
OpenClaw-Cron-Events in `github_state`-WS-Frames umwandelt.

### 3.5 Settings-Overlay, Push-to-Talk, LogPanel, DevPanel etc.

Reines Frontend + kleine Backend-Endpoints. OpenClaw-Web-Control-UI ist eine
andere Baustelle. Alles behalten.

---

## Konkrete Kandidaten zum Löschen (Datei-Liste)

Nach der Aufräum-Runde weg:

```
src/brain/memory/backup.py
src/brain/memory/schema.py
src/brain/memory/store.py              (oder stark schrumpfen)
src/brain/memory/__init__.py           (entsprechend)
src/brain/proactive.py
src/brain/salutation.py
src/brain/response_cache.py
src/brain/response_length.py
src/utils/events.py                    (EventBus)
src/integrations/github/client.py      (→ OpenClaw `github`-Skill)
src/integrations/github/poller.py      (→ OpenClaw-Cron-Job)
src/integrations/github/__init__.py
tests/brain/test_memory_*.py
tests/brain/test_proactive*.py
tests/brain/test_salutation.py
tests/integrations/github/             (komplett)
```

Schrumpfen:

```
src/brain/conversation_mode.py         (~200 → ~50 LOC, nur Sleep-Phrase)
src/brain/intent_parser.py             (SPOTIFY_* + GITHUB_* Intents raus)
src/brain/orchestrator.py              (Spotify/GitHub-Branches raus)
src/api/ws_server.py                   (MemoryStore-Aufrufe raus,
                                       _start_github_poller raus,
                                       broadcast_github_state dünner Adapter,
                                       Welcome-Notification ohne Memory-Probe)
```

`.env`-Aufräumen:

```
GITHUB_TOKEN=                           (→ nicht mehr nötig, `gh auth login` ersetzt es)
```

Summe roh geschätzt: **~2000 LOC raus** (alte Schätzung ~1500 + die zusätzlichen
500 LOC GitHub), bei **mehr** Funktionalität (Memory + Scheduler + GitHub kommen
von OpenClaw, `gh-issues`-Skill gibt uns Sub-Agent-PR-Fixes gratis dazu).

---

## Konfig-Änderungen die das ermöglichen

In `~/.openclaw/openclaw.json` (nicht im JARVIS-Repo):

```json5
{
  agents: {
    defaults: {
      blockStreamingDefault: "on",
      blockStreamingChunk: { minChars: 40, maxChars: 400, breakPreference: "sentence" },
      blockStreamingCoalesce: { minChars: 80, idleMs: 120 },
      memorySearch: { provider: "openai" },   // oder "gemini", "voyage", "mistral"
      sandbox: { enabled: false },
    },
  },
  cron: {
    // Unser ProactiveScheduler als Cron-Jobs neu:
    "calendar-reminder": { spec: "*/1 * * * *", session: "proactive" },
    "vip-mail-check":    { spec: "*/2 * * * *", session: "proactive" },
    // ...
  },
}
```

In `~/.openclaw/workspace/SOUL.md` — Johannes-Sir-Persona + Ton (siehe
bestehende Datei, ggf. Rotations-Hinweis ergänzen).

In `~/.openclaw/workspace/MEMORY.md` — long-term facts über Johannes,
Präferenzen, Decisions (wächst automatisch wenn der Agent „remember that…"
geschrieben bekommt).

---

## Nicht-Ziele dieser Analyse

- **Keine** Implementation jetzt. Das ist nur die Landkarte.
- **Keine** Frontend-Änderung. Das HUD bleibt unverändert.
- **Kein** Fish-Audio-Replace. Die Jarvis-Stimme bleibt auf Fish.
- **Keine** Upstream-Contribution an OpenClaw in diesem Schritt — optional
  für später (Gmail-Skill, Calendar-Skill, Drive-Skill, GitLab-Skill wären
  sinnvolle Kandidaten).

## Reihenfolge-Vorschlag für die Aufräum-Batches

1. **Batch A: Memory-Dedup** — `src/brain/memory/` ausbauen, OpenClaw-Session
   für Archiv nutzen. Risiko: niedrig (Read-Path wird eh nicht benutzt).
2. **Batch B: ProactiveScheduler → OpenClaw-Cron** — Calendar-/Mail-Reminder
   als Cron-Skill neu. Risiko: mittel (Cron-Skill muss HUD-Notification
   zurückpushen können).
3. **Batch C: Persona + Salutation nach SOUL.md** — `salutation.py` löschen.
   Risiko: niedrig.
4. **Batch D: Response-Cache / Length / Block-Streaming-Config** — Gateway
   macht Chunking. Risiko: niedrig.
5. **Batch E: GitHub komplett → `github`-Skill + Cron** — `src/integrations/
   github/` löschen. `gh auth login` ausführen. OpenClaw-Cron-Job für
   State-Broadcast anlegen. Risiko: mittel (neue Integration zwischen Cron
   und HUD-WS). **Behebt gleichzeitig den Rate-Limit-Bug** (unser Code
   nutzt die Search-API mit 30 req/h; `gh` CLI nutzt Core-API mit 5000 req/h).
6. **Batch F: Spotify-Intent delegieren** — Voice-Dispatch an OpenClaw-Skill
   statt lokalem Client. Spotify-HUD-Poller bleibt. Risiko: mittel.

Batches A-D sind unabhängig und können parallel laufen. Batch E braucht
`gh` CLI auf dem Host + `gh auth login`. Batch F braucht
`spogo`/`spotify_player` CLI auf dem Host.
