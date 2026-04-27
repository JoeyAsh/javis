# CLAUDE.md — JARVIS

## Vision
A personal AI assistant in the spirit of Tony Stark's JARVIS — calm, witty, always-on. Built for a single user (senior software engineer & architect) who runs it on Linux, Windows, and macOS workstations and as an always-on companion on a Raspberry Pi 5.

Three pillars:
- **Voice-first companion** — wake word → STT → reasoning → TTS, with barge-in, backchannels, conversation mode, persona. Voice quality matters as much as answer quality.
- **Day & life planning** — daily briefings, calendar/mail coordination, proactive reminders, focus mode, end-of-day review.
- **Programming peer** — pairs with Claude Code and OpenClaw skills to triage PRs, summarise repo activity, capture ADRs by voice, and run review/refactor sessions.

## Stack at a glance
- **JARVIS** owns the voice pipeline (mic, STT, TTS, barge-in, prosody), the React HUD (Orb + panels), the proactive scheduler, persistence (SQLite), and a **local MCP server** that exposes device-specific or non-OpenClaw-covered tools (Spotify, GitHub/GitLab, Home Assistant, PC control, system metrics).
- **OpenClaw** (local clone at `D:/Repos/openclaw`, runtime gateway on the user's Linux laptop, reached via Tailscale) owns the agent runtime: sessions, memory, model routing, tool use, channels (WhatsApp/Telegram/Slack/Signal/iMessage/…), skills, and automation (cron, webhooks). It is the **single source of intelligence** — every voice turn is dispatched here.
- **Claude Code** is the heavyweight coding peer. JARVIS routes non-trivial coding asks through OpenClaw → Claude Code and reads the result back conversationally.

## OpenClaw-First Policy (hard rule)

**Use what OpenClaw offers — do not develop our own when OpenClaw has it.** Single source of truth for agent intelligence. Concretely:

- **For every new feature**, first check `D:/Repos/openclaw/extensions/` (or the docs under `D:/Repos/openclaw/docs/`) whether OpenClaw already provides the capability via a built-in skill, channel, or extension. If yes: integrate via OpenClaw, no parallel implementation in JARVIS.
- **Where OpenClaw does NOT have an equivalent** (Spotify, GitHub, GitLab, Home Assistant, PC control, system metrics): expose the tool as an **MCP server inside the JARVIS backend process** so OpenClaw's agent can call it through the standard MCP protocol. JARVIS is the *tool provider*, OpenClaw is the *intelligence layer*. No tool ever bypasses OpenClaw on the voice path.
- **HUD-Polling stays in JARVIS** for snappy panel UX, but the underlying data fetch should call the same MCP tool (or OpenClaw skill for Google/Web) so there is one code path per data source.
- **Migrate existing parallel implementations** (currently: `src/integrations/google/*`, `src/actions/web_search.py`) to OpenClaw skills.
- The full architectural rationale + MCP placement decision lives in `docs/adr/0001-openclaw-first.md`.

## Conventions
- **Async-first**: all I/O and API calls `async`. Entrypoint: `python -m main` (aiohttp WS server on 8765 / HTTP on 8766; FastAPI is NOT used).
- **Config**: tunable values in `config/config.yaml`. Secrets only via `.env`.
- **Logging**: `loguru` via `src/utils/logger.py`. Never use `print()`.
- **Code style**: `black` + `ruff`, max line 100. Type hints everywhere. Docstrings on all public functions/classes.
- **Error handling**: audio errors → retry with backoff. API errors → spoken fallback. All handlers catch exceptions individually.
- **Testing**: `pytest` + `pytest-asyncio`. Mock all external APIs. No live mic/API calls in unit tests.

## Run
```bash
PYTHONPATH=src .venv/bin/python -m main                                            # backend WS → :8765, HTTP → :8766
cd frontend && npm run dev                                                         # frontend → :5173
docker-compose up --build                                                          # docker
docker-compose -f docker-compose.rpi.yml up --build                               # rpi
```

## Environment Variables
```
ANTHROPIC_API_KEY=sk-ant-...
HOME_ASSISTANT_URL=http://homeassistant.local:8123
HOME_ASSISTANT_TOKEN=...
```

## Orchestrator-Only Policy (hard rule)
Claude (Opus, Haupt-Session) ist **ausschließlich Orchestrator**. Er **schreibt oder editiert niemals selbst** Projekt-Dateien — weder Code noch Config, Tests, Docs, Specs, Shell-Skripte oder `.desktop`/Systemd-Units.
- Jede **Schreib-/Edit-Aktion** (Write, Edit, NotebookEdit, `>`/`>>` in Bash, `sed -i`, `tee`, `cp`/`mv` das Projektdateien erzeugt oder überschreibt) **muss an einen Sonnet-Subagent delegiert werden** (`feature-planner`, `backend-dev`, `frontend-dev`, `tester`, `reviewer` oder `general-purpose` mit `model: sonnet`).
- Erlaubt für den Orchestrator direkt: **lesen** (Read, Glob, Grep, Bash für read-only Commands), **starten/stoppen** von Prozessen und Services, **bauen** (`cargo build`, `npm run build`), **delegieren** (Agent, SendMessage), **planen** (TaskCreate, ScheduleWakeup).
- Einzige Ausnahme: `CLAUDE.md` selbst — Änderungen an dieser Policy-Datei darf der Orchestrator direkt machen, weil es Meta-Config ist.
- Wenn ein Subagent fehlschlägt oder unvollständig abliefert: **erneut delegieren** (SendMessage oder neuer Agent), nicht selbst nachbessern.

## Dev Agents
Einstiegspunkt: **`jarvis-dev`** (Orchestrator, `claude-opus-4-7`). Subagents (alle `claude-sonnet-4-6`):
- `feature-planner` — drafted pro Feature einen Spec als Text. Gibt den Body + Slug + Summary an den Orchestrator zurück, der via Skill `jarvis-publish-issue` ein GitHub-Issue im Backlog anlegt. Kein Code, keine lokalen Dateien.
- `backend-dev` — Python-Backend (audio, brain, actions, FastAPI, WS).
- `frontend-dev` — React/TypeScript/Three.js Frontend.
- `tester` — pytest (+asyncio) Backend, Vitest + RTL Frontend. Externes I/O immer gemockt.
- `reviewer` — finaler Quality-Gate mit `PASS` / `NEEDS_CHANGES`-Verdikt.

Definitionen in `.claude/agents/`.

### Workflow

**Default (lightweight) — gilt für die meisten Tasks:** Branch + Code + **Manual-Test-Pause** + PR. Kein GitHub-Issue. Kein `feature-planner`. Bugfixes, kleine Features, Refactors laufen so:
1. Orchestrator brieft `backend-dev` / `frontend-dev`.
2. Orchestrator restartet die betroffenen Services (Backend + Frontend bei UI-Änderungen, nur Backend bei reinen Backend-Änderungen) und sagt dem User in einer kurzen Zeile, was geändert wurde + bittet ihn um einen manuellen Test (Sprache des Users).
3. **Stopp und warten** bis der User explizit OK gibt (`"passt so"`, `"ok"`, `"ja"`, `"looks good"`, etc.) ODER Feedback zur Iteration kommt. Bei Feedback: zurück zu Schritt 1.
4. Erst nach explizitem User-OK: `tester` (außer bei trivialen 1–2-Zeilen-Fixes), danach `reviewer`, dann **PR anlegen — und stoppen**.

Begründung der Reihenfolge: Tester + Reviewer mocken alles und können UX-Lücken (nicht-getestete Code-Pfade, fehlende Acceptance Criteria) nicht entdecken. Ein 30-Sekunden-Manual-Test des Users hingegen schon. Tests + Review zuerst kostet Tokens für etwas, das der User nachher eh nochmal anfasst.

**Skip-Manual-Test-Ausnahme:** Wenn der User explizit sagt `"weiter ohne manuellen Test"`, `"skip manual"`, oder die Änderung NULL User-Surface hat (rein interner Refactor ohne UI/REST/WS/Voice-Auswirkung), darf der Orchestrator direkt zu Tester + Reviewer übergehen. Default ist *manual test first*. Im Zweifel: pausieren und fragen.

**Nach dem PR-Anlegen** zeigt der Orchestrator dem User die PR-URL und fragt: *"PR steht — soll ich self-reviewen und squash-admin-mergen, oder schaust du selbst rein?"*. Erst auf explizite User-Bestätigung läuft `gh pr review --comment` + `gh pr merge --squash --admin --delete-branch` + lokaler Sync. Niemals Auto-Merge — auch nicht bei Trivial-Fixes — außer der User hat es im selben Auftrag vorab erlaubt.

**Heavy (opt-in, nur wenn der User es ausdrücklich verlangt — Schlüsselwörter wie "mach einen Spec", "leg ein Issue an", "ins Backlog"):**
1. **Planning** — `jarvis-dev` ruft `feature-planner` auf. Planner drafted und retourniert Spec-Body + Slug + Summary. Orchestrator publisht via Skill `jarvis-publish-issue` als GitHub-Issue im Backlog. **Stopp** — keine Implementation, bis der User explizit den Auftrag erteilt.
2. **Implementation** — wie Default-Workflow.
3. **Issue-Lifecycle** — beim Schließen des Issues als completed wird der Project-Board-Eintrag automatisch auf `Done` verschoben (siehe Skill `jarvis-move-issue-status`).

**Definition of Done (beide Modi)** — alle bewussten Acceptance Criteria sind implementiert, alle neuen/geänderten Dateien Tests haben (Trivial-Fixes ausgenommen, wenn explizit so vereinbart), und der finale `reviewer` gibt `PASS` zurück (oder der Orchestrator skippt Review explizit für triviale Fälle und vermerkt das im PR-Body).

**Niemals automatisch** — GitHub-Issue anlegen, Project-Board ändern, Spec im `feature-planner`-Stil draften. Diese drei Schritte passieren nur auf explizite User-Anforderung.

## Issue Lifecycle (Auto-Convention)

When the orchestrator closes an issue on `JoeyAsh/javis` as completed (`gh issue close ... --reason completed`), it MUST in the same batch also transition the project-board item to `Done` via the `jarvis-move-issue-status` skill (option ID `eeaaf043`). Closing without moving leaves the board (`https://github.com/users/JoeyAsh/projects/4`) out of sync — that is a defect. Same rule for `--reason not planned`: move the board item to `Done` (or remove from the board if explicitly out of scope). This is a non-negotiable pairing — never close-only.

When the orchestrator merges a PR that resolves issues (commit body contains `Closes #N`), GitHub auto-closes the issues but does NOT move board items. The orchestrator is still responsible for the board move via `jarvis-move-issue-status`.

## Voice Narration via JARVIS Narration Queue

The JARVIS backend exposes an HTTP endpoint that pushes voice notifications via the NarrationQueue. Use this so JARVIS speaks status updates instead of the user having to poll the chat for results from long-running background work.

**Endpoint** (localhost only): `POST http://127.0.0.1:8766/api/jarvis/notify`

**Curl pattern:**

```bash
curl -s -X POST http://127.0.0.1:8766/api/jarvis/notify \
  -H 'Content-Type: application/json' \
  -d '{"severity":"completion","title":"<short>","body":"<details>","source":"claude-code"}' \
  2>/dev/null || true
```

**Severity guide:**
- `completion` — work finished, voice + HUD, **batched 10 s by `source`** (multiple completions in 10 s with same source merge into one utterance).
- `urgent` — broken state needing immediate attention; voice + HUD with "Verzeihung, Sir — kurz: …" pre-roll.
- `info` — HUD only, no voice (e.g. background poll ticks).
- `update` — HUD + soft chime; voice only when `narration.update_voice: true`.

**When to fire (orchestrator default policy):**
- User explicitly asks to be notified ("sag mir Bescheid wenn fertig", "melde dich wenn der Subagent zurück ist").
- Long-running background subagent (>2 min) returns and the user is genuinely waiting.
- Major workflow milestones the user wants reported (PR opened, merge complete, build/test green/red).

**When NOT to fire:**
- Trivial sub-second steps. Don't narrate every file edit.
- The user is actively in the chat and will see the next response immediately.
- The user has not asked to be told and the work was their direct request (they're already watching).

**Stable source convention:** use `"claude-code"` for general orchestrator notifications; `"claude-code-<issue-num>"` if you need per-issue separation. Coalescing via the 10 s window means redundant completions collapse cleanly.

**Failure handling:** wrap the curl in `2>/dev/null || true` so the orchestrator silently no-ops when the JARVIS backend isn't running. Never let a missing notification block the actual work.

## Skills

Slash-invocable Skills in `.claude/skills/`. Orchestrator und Subagents nutzen sie statt duplizierter Inline-Commands. Aktuelle Skills:

| Skill | Zweck |
|---|---|
| `jarvis-run-dev` | Backend (aiohttp :8765/:8766) + Frontend (Vite :5173) starten, mit Port-Check und Health-Polling. Cross-platform venv-Resolution. |
| `jarvis-tests-run` | pytest + vitest in einem Aufruf, vereinheitlichte PASS/FAIL-Summary. |
| `jarvis-feature-scaffold` | Komplette Frontend-Feature-Folder mit allen Files (Slice/Api/Selectors/Hook/Panel/Tests) emittieren. Rule-compliant by construction. |
| `jarvis-ws-message` | 13-Schritt-Checkliste für neuen WS-Message-Type (Backend-Broadcast → Frontend-Subscribe → Slice → Tests beidseitig). |
| `jarvis-brief-template` | Verbindlicher Delegations-Brief mit MANDATORY-RULES-Block (Quelle: `agents/frontend-dev.md`) + Y/N-Self-Check. Pflicht für jeden frontend-dev-Brief. |
| `jarvis-review-architecture` | Ripgrep-Sweep für alle Architektur-Regeln (interface-in-tsx, multi-component, inline-style, cross-feature-import, …). Severity-grouped Report. |
| `jarvis-fetch-spec` | Issue-Body von `JoeyAsh/javis` fetchen — zentrale Quelle für Dev/Test/Review-Agents. |
| `jarvis-publish-issue` | Spec-Body als GitHub-Issue auf `JoeyAsh/javis` publishen, Label `feature`, Projektboard `Backlog`. Ersetzt den retired `product-owner`-Agent. |
| `jarvis-move-issue-status` | Issue-Status auf dem Projektboard transitionieren (Backlog → … → Done). |
| `jarvis-issue-status` | Schneller Health-Check des Projektboards: alle offenen Issues nach Status gruppiert. |
| `jarvis-symbol-impact` | Via Serena alle Referenzen eines Symbols auflisten — vor jedem Refactor / Signatur-Change. |

Skills werden via Slash-Command oder direkter Aufruf durch den Orchestrator genutzt. Der Orchestrator ruft Skills auch in der Implementation-Phase, um deterministisches Tooling (Tests, GitHub-State) nicht an Sonnet-Subagents zu delegieren.

## Frontend Architecture

Strikte 5-Schichten-Topologie unter `frontend/src/`. Abhängigkeiten fließen **nur in eine Richtung**:

```
app ─► features ─► core ─► ui ─► common
           │                     ▲
           └─────────────────────┘
```

| Layer | Zweck | Darf importieren aus |
|---|---|---|
| `app/` | Komposition: Store, Providers, Shell (TopBar/Dock/OrbStage), Panel-Registry | features, core, ui, common |
| `features/<name>/` | Eine Domäne (mail, agenda, gitlab, system, …). **Features importieren sich niemals gegenseitig.** | core, ui, common |
| `core/` | Runtime-Infrastruktur (`websocket`, `audio`, `tauri`, `storage`, `api`) | ui, common |
| `ui/` | Echte UI-Lib — Primitives, Compositions, Window-System, Orb-Visuals. **Kennt weder Features noch Store.** | common |
| `common/` | Cross-Feature-Utilities, Shared-Types (`OrbState`, `PanelId`, `SlotId`), kleine Hooks | — |

Zugriff ausschließlich über Public-Barrels. Deep-Imports verboten (ESLint-enforced).

### State & API

- **Global State: Redux Toolkit**. `configureStore` in `app/store.ts`, Slices in `features/<name>/<name>Slice.ts`. Selectors via `createSelector`. Kein React-Context für Shared-State.
- **REST: RTK Query**. Endpoints in `features/<name>/<name>Api.ts`, `injectEndpoints` in `core/api/baseApi.ts`. **Niemals `fetch()` direkt, niemals `axios`.**
- **WebSocket-Streams: RTK Query Streaming Queries** via `onCacheEntryAdded` + `updateCachedData`. Singleton-Client in `core/websocket/wsClient.ts`. Ausnahme: Binär-Mic-Upload + TTS-Audio-Queue bleiben raw WS in `core/audio/` (Barge-in + Queue-Flush passen nicht ins Cache-Modell).
- **OpenAPI-Codegen**: bewusst deaktiviert. Endpoints werden aktuell manuell geschrieben. Migration auf `@rtk-query/codegen-openapi` folgt nach Backend-Refactor.

### Component Rules

Die vollständigen, verbindlichen Komponenten-Regeln (12 Punkte: `interface` für Props, Types in `.types.ts`, eine Komponente pro Datei, Tailwind-first, keine Inline-Styles, keine direkten `fetch`/`axios`/`new WebSocket`, strikt TypeScript, etc.) liegen in `.claude/agents/frontend-dev.md` unter "MANDATORY RULES" und sind die Single Source of Truth. Subagents lesen sie dort. Auch der Skill `jarvis-brief-template` zieht aus dieser Quelle.

Kurzform für den Orchestrator:
- 1 Komponente pro Datei, Types in `<Component>.types.ts`, Helper in `utils.ts`/`constants.ts`.
- Tailwind first, `.module.css` nur mit Justification-Kommentar.
- Kein `fetch`/`axios`/`new WebSocket()` außerhalb `@core/api/*` und `@core/websocket/wsClient.ts`.
- Strikt TypeScript: kein `any`/`!`/`@ts-ignore`. Named + Default Export.
- `@ui/orb/orbEngine.ts` ist eingefroren.

### Feature-Anatomie

```
frontend/src/features/<name>/
├── components/
│   └── <PascalComponent>/
│       ├── <PascalComponent>.tsx
│       ├── <PascalComponent>.types.ts
│       ├── <PascalComponent>.module.css     # optional, nur wenn Tailwind nicht reicht
│       └── index.ts
├── hooks/
│   └── use<Feature>.ts
├── <name>Slice.ts
├── <name>Api.ts                              # RTK Query (streaming + REST)
├── <name>Selectors.ts
├── types.ts                                   # Domain-Typen + WS-Payloads
├── mock.ts
├── index.ts                                   # Public API: Components + Hook + Types
└── __tests__/
```

### Path Aliases (tsconfig + vite + eslint)

```
@app/*       → src/app/*
@features/*  → src/features/*
@core/*      → src/core/*
@ui          → src/ui            (Public Barrel)
@ui/*        → src/ui/*          (intern, nicht aus features/core nutzen)
@common/*    → src/common/*
@test/*      → src/test/*
```


## Further Docs
- Architecture & runtime agents: `docs/ARCHITECTURE.md`
- UI/UX design guidelines & visual language: `docs/DESIGN.md`
- Frontend design system & components: `docs/FRONTEND.md`
- Full implementation spec: `docs/PROJECT_DESCRIPTION.md`
