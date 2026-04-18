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

## Dev Agents
Einstiegspunkt: **`jarvis-dev`** (Orchestrator, `claude-opus-4-7`). Subagents (alle `claude-sonnet-4-6`):
- `feature-planner` — schreibt pro Feature einen Spec nach `.tmp/features/<slug>.md` (Goal, Scope, Architecture, Interfaces, Edge Cases, Acceptance Criteria, Implementation Plan). Kein Code.
- `backend-dev` — Python-Backend (audio, brain, actions, FastAPI, WS).
- `frontend-dev` — React/TypeScript/Three.js Frontend.
- `tester` — pytest (+asyncio) Backend, Vitest + RTL Frontend. Externes I/O immer gemockt.
- `reviewer` — finaler Quality-Gate mit `PASS` / `NEEDS_CHANGES`-Verdikt.

Definitionen in `.claude/agents/`.

### Workflow
1. **Planning** — Neue Feature-Idee → `jarvis-dev` ruft `feature-planner`. Spec landet in `.tmp/features/`. **Stopp** — keine Implementation, bis der User explizit den Auftrag erteilt.
2. **Implementation** (nur nach Freigabe) — `jarvis-dev` arbeitet den Implementation Plan Schritt für Schritt ab: `backend-dev` / `frontend-dev` → `tester` → `reviewer`. Bei `NEEDS_CHANGES` wird der jeweilige Dev-Agent mit dem Review-Report erneut angerufen (max. 3 Zyklen pro Batch).
3. **Definition of Done** — Feature gilt nur als fertig, wenn **alle** Acceptance Criteria implementiert sind, alle neuen/geänderten Dateien Tests haben und der finale `reviewer` `PASS` zurückgibt. Keine stillschweigenden Auslassungen, keine Restarbeit für den User.

## Further Docs
- Architecture & runtime agents: `docs/ARCHITECTURE.md`
- UI/UX design guidelines & visual language: `docs/DESIGN.md`
- Frontend design system & components: `docs/FRONTEND.md`
- Full implementation spec: `docs/PROJECT_DESCRIPTION.md`
