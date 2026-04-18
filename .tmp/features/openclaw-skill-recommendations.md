# OpenClaw Skill-Empfehlungen für JARVIS

**Stand 2026-04-18. Quellen: `http://127.0.0.1:18789/skills` (installiert) + `https://clawhub.ai` (Marketplace, 56.363 Skills).**

Ergänzt `openclaw-dedup-analysis.md`. Die Dedup-Analyse sagt *was raus kann*; dieses Dokument sagt *was rein kann*. Alles hier ist eine Empfehlung — nichts wird implementiert, bis du grünes Licht gibst.

## Bereits installiert (Workspace Skills)

| Skill | Quelle | Status |
|---|---|---|
| `google-calendar` | Workspace | aktiv — JARVIS-Calendar-Client kann darauf umstellen |
| `google-drive` | Workspace | aktiv — JARVIS-Drive-Client kann darauf umstellen |
| `lastpass-cli` | Workspace | aktiv — kein JARVIS-Gegenstück bisher |

Damit können unsere eigenen `CalendarClient` + `DriveClient` Module langfristig ersetzt werden (HUD-Poller separat betrachten, siehe Dedup-Analyse Tier 2).

---

## Built-in OpenClaw Skills (52 — schon verfügbar, kein Install nötig)

Diese sind immer da; der Agent kann sie direkt via Tool-Use aufrufen. Empfehlungen nach Relevanz:

### Stark relevant für JARVIS

- **`github`** 🐙 — **`gh` CLI Wrapper. Deckt PRs, Issues, CI-Runs, Code-Review, API-Queries komplett ab.** Kann unseren kompletten `src/integrations/github/` Ordner (`client.py` + `poller.py`, ~500 LOC + 36 Tests) ersetzen. Auth läuft über `gh auth login` statt PAT in `.env` — das ist sogar der saubere Weg. Siehe auch Dedup-Analyse Update unten. **Voraussetzung: `gh` CLI installieren.**
- **`gh-issues`** — Issue-Workflow-Skill mit Sub-Agent: spawnt Sub-Agents, die Issues fixen + PRs öffnen. **Killer-Feature**, haben wir nie selbst gebaut.
- **`gog`** 🎮 — Google Workspace CLI für Gmail, Calendar, Drive, Contacts, Sheets, Docs in einem. *Könnte `google-calendar` + `google-drive` + ein zukünftiges Gmail-Skill zusammenfassen.*
- **`spotify-player`** 🎵 — `spogo`/`spotify_player` CLI. Kann unsere Spotify-Voice-Intents ersetzen (HUD-Poller bleibt für Live-State).
- **`openai-whisper`** 🎤 — Lokales Whisper STT (kein API-Key). Alternative zu `faster-whisper` — aber unser Setup läuft, also nicht eilig.
- **`summarize`** 🧾 — Zusammenfassungen für Mails, Docs, YouTube. *Perfekt für „Jarvis, fass die E-Mail zusammen".*
- **`healthcheck`** — System-Hardening-Audit (Firewall, SSH, Updates).
- **`session-logs`** 📜 — durchsucht JARVIS-Session-Logs.
- **`voice-call`** 📞 — Twilio/Telnyx-Anrufe starten.

### Nett zu haben (JARVIS-nah)

- **`himalaya`** 📧 — IMAP/SMTP-Client. Alternative zu Gmail-API wenn wir mal IMAP brauchen.
- **`notion`** 📝 / **`obsidian`** 💎 / **`bear-notes`** 🐻 — Notes-Integrationen falls du einen dieser Services nutzt.
- **`1password`** 🔐 — Alternative/Komplement zu deinem LastPass.
- **`weather`** — einfacher Wetter-Skill (wir haben bereits Open-Meteo im Frontend → redundant).
- **`model-usage`** 📊 — Cost-Tracking für Codex/Claude.
- **`skill-creator`** — hilft dabei, eigene Skills zu bauen (z.B. einen Gmail-Custom-Skill).

### Nicht relevant für uns

- Apple-spezifisch: `apple-notes`, `apple-reminders`, `things-mac`, `imsg`, `bluebubbles`, `peekaboo`, `sag` (macOS TTS) — du bist auf Linux.
- Sonos/BluOS/Eight Sleep — andere Geräte.
- `nano-pdf`, `gifgrep`, `video-frames`, `songsee` — Media-Tools, kein Fit.
- `clawhub` — Management-CLI für den Marketplace selbst (schon indirekt verfügbar).

---

## Empfehlungen aus ClawHub (noch nicht installiert)

Sortiert nach Kategorie. Download-Zahlen sind grober Qualitäts-Indikator.

### 🏠 Smart Home (für den geparkten Govee/Home-Assistant-Weg)

| Skill | Autor | Downloads | Kommentar |
|---|---|---|---|
| **Home Assistant** | @iahmadzain | 17.1k ★41 | Top-Pick. REST API out + Webhooks in. Lights/Switches/Climate/Scenes. |
| **Home Assistant Agent (Secure)** | @szafranski | 1.3k ★2 | Nutzt HA's Assist-Conversation-API (natürliche Sprache) — sicherer als REST-direkt. |
| **Home Assistant Integration** | - | - | Alternative Implementation — check README welches besser passt. |
| **Philips Hue** | @aprilox | 655 | Lokale API v1 Kontrolle. Alternative zu `openhue` im built-in. |
| **Philips Hue Thinking Indicator** | @jesserod329 | 1.7k ★1 | **Coole Idee für JARVIS**: pulst rot wenn der Agent denkt, grün wenn fertig. Visuelle Rückkopplung jenseits des Orbs. |

**Empfehlung:** Home Assistant (@iahmadzain) installieren, sobald du eine HA-Instanz hast. Ersetzt unseren parkierten `smart_home_agent.py`.

### 📧 Mail (spezialisiertere Alternativen zu `gog`)

| Skill | Autor | Downloads | Kommentar |
|---|---|---|---|
| **Gws Gmail** | @googleworkspace-bot | 2.5k | Offizieller Gmail-Skill — Send, read, manage. |
| **Gmail Secretary** | @officialdelta | 2.1k | Triage mit Haiku-LLM, Label-Application, Draft-Replies. **Nutzt gog CLI, nie Auto-Send.** Passt zu unserem „confirmation gate"-Muster. |
| **Gws Gmail Send** | @googleworkspace-bot | 997 | Nur-Senden-Variante. |

**Empfehlung:** `gog` (built-in) reicht für den Anfang. Gmail Secretary später hinzunehmen für smartes Triage.

### 🐙 GitHub — **höchste Priorität, löst Rate-Limit-Bug**

| Skill | Autor | Downloads | Kommentar |
|---|---|---|---|
| **`github`** (built-in) | @steipete | — | **Primär-Empfehlung**. `gh` CLI Wrapper, Core-API (5000 req/h statt 30 req/h Search-API). Ersetzt den kompletten `src/integrations/github/`. |
| **`gh-issues`** (built-in) | — | — | **Extra**: spawnt Sub-Agents, die Issues fixen + PRs öffnen. Haben wir nie selbst gebaut. |

**Setup:**
```bash
# gh CLI installieren (falls noch nicht da)
sudo apt install gh

# einmalig authentifizieren (ersetzt GITHUB_TOKEN in .env)
gh auth login
```

**Empfehlung:** Komplett auf `github`-Skill umstellen. **Behebt gleichzeitig den Rate-Limit-Bug**, den unser Custom-Client gerade produziert (unsere `/search/issues`-Aufrufe sind auf 30 req/h gedeckelt, deshalb läuft der Poller in 240s-Backoffs). `gh` CLI nutzt die Core-API. Details in Dedup-Analyse Tier 1.5.

### 🦊 GitLab — **OpenClaw hat kein Built-in, ClawHub-Skills nötig**

| Skill | Autor | Downloads | Kommentar |
|---|---|---|---|
| **gitlab-cli-skills** | @vince-winkintel | 4.7k ★6 | `glab` CLI Wrapper — umfassender. **Parität zu GitHub-Weg.** |
| **Gitlab Manager** | @jorgermp | 3.2k ★5 | Direkt API-basiert. |
| **GitLab API** | @d1gl3 | 2k | Read/Write Files, Branches, Projects. |
| **GitLab Code Review** | @zhanghaiyu0511 | 702 | Cron-basiert automatisches Review mit Reports. |

**Setup:**
```bash
sudo apt install glab    # GitLab CLI
glab auth login          # ersetzt GITLAB_TOKEN in .env bei Voll-Migration
openclaw skills install gitlab-cli-skills
```

**Empfehlung:** `gitlab-cli-skills`. Unser JARVIS-GitLab-Poller bleibt fürs HUD, Voice-Dispatch geht via Skill. GitLab bleibt Tier 3 in der Dedup-Analyse (eigener Python-Code bleibt, weil kein Built-in da ist).

### 🎵 Spotify

| Skill | Autor | Downloads | Kommentar |
|---|---|---|---|
| **Spotify History** | @braydoncoyer | 2.7k ★4 | Listening-History, Top-Artists, Recommendations. OAuth-basiert. **Mehr als nur Playback.** |
| **Spotify** | @shawnpana | 1.8k | Playback-Kontrolle Linux-freundlich via CLI. |

**Empfehlung:** Eventuell `Spotify History` zusätzlich — damit JARVIS sagen kann „du hörst heute viel X, passt zur Stimmung Y".

### 🧠 Memory (Ersatz für `src/brain/memory/`)

| Skill | Autor | Downloads | Kommentar |
|---|---|---|---|
| **Elite Longterm Memory** | @nextfrontierbuilds | **52k ★196** | WAL-Protokoll + Vector-Search + Git-Notes + Cloud-Backup. Top-Download. |
| **Neural Memory** | @nhadaututtheky | 8.6k ★9 | Assoziatives Gedächtnis mit Spreading Activation für intelligenten Recall. |
| **Memory Tiering** | @sarielwang93 | 12k ★6 | HOT/WARM/COLD-Tiers mit automatischem Pruning. |
| **Memory Hygiene** | @dylanbaker24 | 18.5k ★18 | Säubert die Vector-Memory-Datenbank regelmäßig. **Kombiniert gut mit anderen Memory-Skills.** |

**Empfehlung:** `Elite Longterm Memory` + `Memory Hygiene`. Ersetzt unser SQLite-Archiv komplett und liefert gleich Vector-Search + Backup.

### 🤖 Proaktiv-Scheduler (Ersatz für `src/brain/proactive.py`)

| Skill | Autor | Downloads | Kommentar |
|---|---|---|---|
| **Proactive Agent Lite** | @bestrocky | **33.4k ★54** | Reverse Prompting + Self-Healing. Leichtgewichtig. |
| **Proactive Agent Skill** | @fangkelvin | 14.8k ★9 | WAL-Protokoll + Working Buffer + autonome Task-Execution. |
| **Self-Improving Proactive Agent** | @yueyanc | 10.2k ★8 | Merged Self-Improvement + Proactivity, lernt aus Korrekturen. |
| **Proactive Tasks** | - | - | Goal-Management, Heartbeat-basiert. |
| **Cron & Scheduling** | @gitgoodordietrying | 8.3k ★7 | Cron + systemd-Timer, Timezone-aware, Retry-Patterns. |

**Empfehlung:** `Proactive Agent Lite` + `Cron & Scheduling`. Zusammen ersetzen sie unsere `ProactiveScheduler` + `EventBus` + Timer-Loops.

### 📰 News / RSS

| Skill | Autor | Downloads | Kommentar |
|---|---|---|---|
| **Rss Ai Reader** | @benzema216 | 6.1k ★14 | LLM-generierte Summaries aus RSS, pusht an Feishu/Telegram/Email. |
| **RSS Reader** | @dimitripantzos | 3.8k ★2 | Blogs, News-Sites, Newsletter-Monitoring. |
| **Rss Digest** | @odysseus0 | 3.7k ★2 | Agentic, mit `feed` CLI, sortiert nach Signal-Qualität. |
| **blogwatcher** (built-in) | @steipete | - | Schon da — einfachere RSS-Überwachung. |

**Empfehlung:** `blogwatcher` (built-in) für Basic-Monitoring, `Rss Ai Reader` wenn du LLM-Summaries für morgendliches Briefing willst („Jarvis, was gibt's Neues?").

### 🌤️ Wetter (optional)

| Skill | Autor | Downloads | Kommentar |
|---|---|---|---|
| **Weather Pollen** | @thesethrose | 4.5k ★2 | + Pollen-Daten. |
| **Weather via OpenMeteo (advanced)** | @lstpsche | 1.7k ★2 | Historisch, detaillierte Variablen. |
| **Weather 1.0.0** | @99percentgod | 1.9k ★1 | wttr.in + Open-Meteo, kein API-Key. |

*Wir haben Wetter bereits im HUD (Open-Meteo im Frontend) — Skills sind nur nötig wenn JARVIS das per Voice abrufen soll.*

### 💻 System / Docker (für DevPanel-Erweiterung)

| Skill | Autor | Downloads | Kommentar |
|---|---|---|---|
| **Docker Essentials** | @arnarsson | 27.6k ★30 | Container-Management, Image-Ops, Debugging. |
| **Docker Compose** | @ivangdavila | 5k ★3 | Multi-Container-Apps, Networking, Volumes. |
| **Linux** | @ivangdavila | 3k ★5 | Permission-Traps, Silent-Failures vermeiden. |
| **Sysadmin** | - | - | Server-Management, User-Admin, Process-Control. |
| **System Info** | @xejrax | 8.4k ★8 | Quick Diagnostics CPU/RAM/Disk/Uptime. **Wir haben das im HUD, aber für Voice:** „Jarvis, wie steht's um die Kiste?" |

**Empfehlung:** `Docker Essentials` + `System Info` + `Linux`. Gibt JARVIS konkrete Dev-Ops-Power via Voice.

### 🛡️ Security (wichtig!)

| Skill | Autor | Downloads | Kommentar |
|---|---|---|---|
| **Skill Vetter** | @spclaudehome | 212k ★912 | **Vor jedem Install aus ClawHub laufen lassen.** Security-first Vetting: Red Flags, Permission-Scope, suspicious Patterns. |

**Empfehlung:** **Unbedingt zuerst installieren**, bevor du andere ClawHub-Skills aus unbekannten Autoren nimmst.

### 🔊 TTS (Fish Audio bleibt Primary, aber als Fallback)

| Skill | Autor | Downloads | Kommentar |
|---|---|---|---|
| **Edge TTS** | @i3130002 | 17.4k ★28 | Microsoft Edge TTS, frei, multi-lingual. |
| **OpenAI TTS** | @pors | 6.2k ★6 | Via OpenAI Speech API. |
| **Kokoro TTS** | - | - | Lokales TTS, offline. |
| **sherpa-onnx-tts** (built-in) | @steipete | - | Lokal, offline. |

*Fish Audio bleibt die Jarvis-Stimme. Diese Skills nur als Notfall-Fallback wenn Fish down ist oder du Mehrsprachigkeit brauchst.*

### 🎨 Utilities / Fun

| Skill | Autor | Downloads | Kommentar |
|---|---|---|---|
| **Ontology** | @oswalpalash | 167k ★543 | Getypter Knowledge-Graph — strukturiert JARVIS' Wissen über dich (Personen, Projekte, Tasks, Events). **Extrem stark zu kombinieren mit Memory.** |
| **Self-Improving Agent** | @pskoett | 397k ★3.2k | Lernt aus Fehlern und Korrekturen. Meistgeladene Skill überhaupt. |
| **Humanizer** | @biostartechnology | - | Macht Agent-Output weniger roboterhaft — könnte bei JARVIS' „British butler"-Stil stören, also nicht blind installieren. |
| **Tavily Search** | @jacky1n7 | - | Web-Search — JARVIS hat bisher keine Websuche. |
| **Multi Search Engine** | @gpyangyoujun | - | 16 Engines gleichzeitig. |

**Empfehlung:** `Self-Improving Agent` + `Ontology` sind stark. `Tavily Search` macht Sinn wenn JARVIS Websuche können soll.

---

## Kurzfassung: Installations-Prioritätenliste

### Stufe 1 — sofort sinnvoll (geringes Risiko, hoher Nutzen)

```bash
# Sicherheit zuerst
openclaw skills install skill-vetter

# GitHub-Ausbau (löst Rate-Limit-Bug gleichzeitig)
sudo apt install gh
gh auth login                              # ersetzt GITHUB_TOKEN in .env
# `github` + `gh-issues` sind BUILT-IN — nichts extra zu installieren

# built-ins aktivieren
openclaw skills install gog                # Google-Workspace CLI
openclaw skills install self-improving-agent
openclaw skills install docker-essentials
openclaw skills install system-info
```

### Stufe 2 — wenn du die Memory-Migration (Dedup-Batch A) angehst

```bash
openclaw skills install elite-longterm-memory
openclaw skills install memory-hygiene
```

### Stufe 3 — wenn du Proactive-Scheduler-Migration (Dedup-Batch B) angehst

```bash
openclaw skills install proactive-agent-lite
openclaw skills install cron-scheduling
```

### Stufe 4 — Feature-Erweiterungen

```bash
# GitLab-Parität zum GitHub-Weg
sudo apt install glab
glab auth login
openclaw skills install gitlab-cli-skills

# Smart Home + Web + News
openclaw skills install home-assistant        # wenn HA-Instanz da ist
openclaw skills install tavily-search         # Websuche
openclaw skills install blogwatcher           # built-in, nur aktivieren
openclaw skills install rss-ai-reader         # morgendliches News-Briefing
```

### Stufe 5 — nice-to-have

```bash
openclaw skills install spotify-history
openclaw skills install gmail-secretary
openclaw skills install ontology
openclaw skills install philips-hue-thinking-indicator  # reines Gimmick, aber geil
```

---

## Wie das zu `openclaw-dedup-analysis.md` passt

| Dedup-Batch | Benötigter Skill | Setup-Voraussetzung |
|---|---|---|
| Batch A — Memory-Dedup | `elite-longterm-memory` + `memory-hygiene` | — |
| Batch B — Proactive → Cron | `proactive-agent-lite` + `cron-scheduling` | — |
| Batch C — Persona → SOUL.md | keine Skill-Abhängigkeit | — |
| Batch D — Response-Cache/Streaming | keine Skill-Abhängigkeit (Gateway-Config) | — |
| **Batch E — GitHub komplett ersetzen** | built-in `github` + `gh-issues` | `gh` CLI + `gh auth login` |
| Batch F — Spotify-Intent delegieren | built-in `spotify-player` | `spogo` oder `spotify_player` CLI |

Zusätzliches Potenzial jenseits der Dedup-Analyse:
- Home Assistant live anbinden → smart_home_agent.py reaktivieren + HA-Skill nutzen
- Websuche via Tavily → neuer Intent im Frontend + LLM-Tool-Use
- Gmail Secretary → smarteres Triage für den vorhandenen MailPanel

## Sicherheitshinweis

ClawHub-Skills werden von Community-Autoren veröffentlicht und können Code ausführen. **Skill Vetter** zuerst installieren und benutzen. Offizielle Skills (`@steipete`, `@googleworkspace-bot`, Built-ins) sind safer. Bei unbekannten Autoren: Skill-Quelle vor Install prüfen.
