# CLAUDE.md — JARVIS

## Project
Voice-activated AI assistant. Wake word → STT → Claude API → TTS. PC control + Smart Home. Runs locally, Docker, Raspberry Pi.

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
- `feature-planner` — drafted pro Feature einen Spec als Text und übergibt ihn per `SendMessage` an `product-owner`, der ihn als GitHub-Issue im Backlog veröffentlicht. Kein Code, keine lokalen Dateien.
- `backend-dev` — Python-Backend (audio, brain, actions, FastAPI, WS).
- `frontend-dev` — React/TypeScript/Three.js Frontend.
- `tester` — pytest (+asyncio) Backend, Vitest + RTL Frontend. Externes I/O immer gemockt.
- `reviewer` — finaler Quality-Gate mit `PASS` / `NEEDS_CHANGES`-Verdikt.

Definitionen in `.claude/agents/`.

### Workflow
1. **Planning** — Neue Feature-Idee → `jarvis-dev` öffnet ein Agent-Team und ruft `feature-planner` + `product-owner` darin. Planner drafted, schickt per `SendMessage` an den PO, der eine GitHub-Issue im Backlog anlegt. **Keine lokalen Spec-Dateien mehr.** **Stopp** — keine Implementation, bis der User explizit den Auftrag erteilt.
2. **Implementation** (nur nach Freigabe) — `jarvis-dev` arbeitet den Implementation Plan Schritt für Schritt ab: `backend-dev` / `frontend-dev` → `tester` → `reviewer`. Bei `NEEDS_CHANGES` wird der jeweilige Dev-Agent mit dem Review-Report erneut angerufen (max. 3 Zyklen pro Batch).
3. **Definition of Done** — Feature gilt nur als fertig, wenn **alle** Acceptance Criteria implementiert sind, alle neuen/geänderten Dateien Tests haben und der finale `reviewer` `PASS` zurückgibt. Keine stillschweigenden Auslassungen, keine Restarbeit für den User.

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

### Komponenten-Regeln (non-negotiable)

- **Eine Komponente pro Datei.** Kein zweiter `function Foo` oder `const Foo: FC = ...` im selben `.tsx`.
- **Keine Typen in `.tsx` oder Hook-`.ts`-Dateien.** Jede `interface`-, `type`- und `enum`-Deklaration lebt in `<Component>.types.ts` neben der `.tsx`. Das gilt auch für Union-Types (`type TabId = 'a' | 'b'`), "kleine" Aliases und Helper-Component-Props. Keine "private" oder "klein"-Ausnahme.
- **Keine Top-Level-Hilfsfunktionen in `.tsx`.** Util-Funktionen, Formatter, Classifier, Type Guards und kleine interne Helpers gehören in eine Geschwister-Datei `utils.ts` (oder spezifischer: `format.ts`, `classify.ts`). Ein `function foo(...)` oder `const foo = (...)` (Kleinbuchstabenstart) auf Modulebene in einer `.tsx` ist ein KRITISCHER Verstoß.
- **Modul-Level-Konstanten in `.tsx`: nur komponenten-lokale Lookup-Tabellen.** Erlaubt sind Style-/Config-Lookups wie `VARIANT_CLASSES`, `SIZE_CLASSES`, `PARTICLE_CONFIGS`, `TICK_ANGLES` — strikt an **eine** Komponente gebunden, nur von ihr konsumiert. Verboten sind numerische Schwellen (`MIN_W = 180`), Timings (`TIMEOUT_MS = 10_000`) und cross-component-Werte — die gehören in `constants.ts` daneben. Faustregel: wird der Wert außerhalb der Komponente gebraucht oder ist es eine Zahl/ein Zeitwert, raus damit.
- **Keine Inline-Styles.** Einzige Ausnahme: CSS-Variablen-Injection, z. B. `style={{ '--panel-opacity': x } as React.CSSProperties}`.
- **Tailwind first, CSS Modules bei Bedarf.** Keyframes, Blend-Modes, komplexe Gradienten dürfen in `<Component>.module.css` — ausschließlich von dieser Komponente konsumiert. **Kein globales `import './Foo.css'`.**
- **Named export + default export** auf jeder Komponente.
- **Strikt TypeScript**: kein `any`, kein `!`, kein `@ts-ignore`. Fehlt ein Type, wird er geschrieben.

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

### Verboten (ESLint `no-restricted-imports` auf `error`)

- Feature-zu-Feature-Imports
- Deep-Imports in `@ui` — nur `import { Button } from '@ui'`
- `fetch()` / `axios` direkt — immer RTK Query
- Globale `import './Foo.css'` — nur scoped `.module.css`
- Mehr als eine Komponente pro Datei
- Interfaces in `.tsx`-Dateien
- Inline-Styles (außer CSS-Variablen-Injection)
- `any`, `!`, `@ts-ignore`
- `border-radius > 4px`
- Änderungen an `src/ui/orb/orbEngine.ts` (Three.js-Engine — black box)

## Further Docs
- Architecture & runtime agents: `docs/ARCHITECTURE.md`
- UI/UX design guidelines & visual language: `docs/DESIGN.md`
- Frontend design system & components: `docs/FRONTEND.md`
- Full implementation spec: `docs/PROJECT_DESCRIPTION.md`
