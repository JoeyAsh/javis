# CLAUDE.md — JARVIS

## Project
Voice-activated AI assistant. Wake word → STT → Claude API → TTS. PC control + Smart Home. Runs locally, Docker, Raspberry Pi.

## Conventions
- **Async-first**: all I/O and API calls `async`. Entrypoint: `asyncio.run(main())`.
- **Config**: tunable values in `config/config.yaml`. Secrets only via `.env`.
- **Logging**: `loguru` via `src/utils/logger.py`. Never use `print()`.
- **Code style**: `black` + `ruff`, max line 100. Type hints everywhere. Docstrings on all public functions/classes.
- **Error handling**: audio errors → retry with backoff. API errors → spoken fallback. All handlers catch exceptions individually.
- **Testing**: `pytest` + `pytest-asyncio`. Mock all external APIs. No live mic/API calls in unit tests.

## Run
```bash
python src/main.py                                      # local
docker-compose up --build                               # docker
docker-compose -f docker-compose.rpi.yml up --build    # rpi
cd frontend && npm run dev                              # frontend → :5173
```

## Environment Variables
```
ANTHROPIC_API_KEY=sk-ant-...
HOME_ASSISTANT_URL=http://homeassistant.local:8123
HOME_ASSISTANT_TOKEN=...
```

## Dev Agents
Einstiegspunkt: **`jarvis-dev`** (Orchestrator, claude-opus-4-5). Subagents: `architecture`, `code`, `test`, `review`, `docs`, `refactor`, `design` — alle claude-sonnet-4-6. Definitionen in `.claude/agents/`.

## Further Docs
- Architecture & runtime agents: `docs/ARCHITECTURE.md`
- UI/UX design guidelines & visual language: `docs/DESIGN.md`
- Frontend design system & components: `docs/FRONTEND.md`
- Full implementation spec: `docs/PROJECT_DESCRIPTION.md`
