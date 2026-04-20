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

## Further Docs
- Architecture & runtime agents: `docs/ARCHITECTURE.md`
- UI/UX design guidelines & visual language: `docs/DESIGN.md`
- Frontend design system & components: `docs/FRONTEND.md`
- Full implementation spec: `docs/PROJECT_DESCRIPTION.md`
