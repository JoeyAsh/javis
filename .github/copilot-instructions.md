# Copilot Instructions — JARVIS

## Project
Voice-activated AI assistant. Wake word → STT → Claude API → TTS. PC control + Smart Home. Runs locally, Docker, Raspberry Pi.

## Tech Stack
- **Backend:** Python 3.12+, asyncio, aiohttp (WS on :8765, HTTP on :8766). **Not FastAPI.**
- **Frontend:** React 18 + TypeScript (strict), Vite, Three.js (orb), Tailwind CSS
- **Testing:** pytest + pytest-asyncio (backend), Vitest + React Testing Library (frontend)
- **Formatting:** black + ruff, max line length 100
- **Logging:** loguru via `src/utils/logger.py` — never use `print()` or `import logging`

## Coding Conventions

### Python (Backend)
- **Async-first:** all I/O and API calls must be `async def`. No blocking calls (`time.sleep`, sync `requests`, sync file I/O) inside async functions. Use `asyncio.to_thread` for unavoidable sync libs.
- **Type hints everywhere:** parameters, returns, class attributes. Use `from __future__ import annotations` where helpful.
- **Config:** tunable values in `config/config.yaml`. Secrets only via `.env`. Never read `os.environ` directly in feature code — use the config loader.
- **Error handling:** catch specific exceptions (no bare `except`). Audio errors → retry with backoff. API errors → spoken fallback. All handlers catch exceptions individually.
- **Docstrings:** on all public functions, methods, and classes.
- **No hardcoded values:** no magic strings/numbers. Use config or constants.
- **Dependency injection:** constructors take their dependencies. No new global singletons.

### TypeScript / React (Frontend)
- **Strict TypeScript:** no `any`, no `!` non-null assertions, no `// @ts-ignore`.
- **Explicit `interface`** for every props object. Named AND default export on every component.
- **Colors only via CSS variables** — never hardcode hex values. Tailwind for layout/spacing only.
- **JetBrains Mono** font only. `border-radius` ≤ 4px (sharp HUD aesthetic).
- **Never modify `frontend/src/lib/orb.ts`** — interact via its public API only.
- **Hook rules:** no conditional hooks, cleanup in `useEffect` returns, stable dependency arrays.
- **Loading and error states** handled explicitly for any async data component.

### Testing
- `@pytest.mark.asyncio` on every async Python test.
- **Mock all external I/O:** Anthropic client, audio devices, Home Assistant, subprocess, WebSocket, fetch, orb.
- No flaky timing (`sleep` hopes). Use `asyncio.Event`, `await`, or fake clocks.
- Descriptive test names: `test_<function>_<scenario>_<expected>` (Python), `it('<subject> <scenario> <expected>')` (frontend).
- Coverage: happy path, empty/None input, every exception path, spec edge cases.

## Project Layout
```
src/
  audio/          # Audio I/O and models (STT, TTS, wake word)
  brain/          # Claude client, prompt plumbing, orchestrator
  actions/        # Home Assistant, PC control
  api/            # aiohttp WS + HTTP server (ws_server.py)
  integrations/   # OpenClaw, Spotify, Google, GitHub, GitLab
  utils/          # Logger, config loader, helpers
  main.py         # Entry point: python -m main
config/
  config.yaml     # All tunable settings
frontend/
  src/components/  # One .tsx per component
  src/hooks/       # One .ts per hook
  src/lib/         # Orb engine (DO NOT MODIFY), utilities
tests/             # Mirrors src/ structure
```

## Run Commands
```bash
# Backend (Windows PowerShell)
$env:PYTHONPATH="src"; .\.venv\Scripts\python.exe -m main

# Backend (Linux/macOS)
PYTHONPATH=src .venv/bin/python -m main

# Frontend
cd frontend && npm run dev

# Tests
PYTHONPATH=src pytest tests/
cd frontend && npx vitest
```

## Design System (CSS Variables)
```css
--bg:            #050508;
--surface:       #0d0d14;
--surface-raised:#12121c;
--border:        #1a1a2e;
--accent:        #4ca8e8;
--accent-bright: #6ec4ff;
--accent-speak:  #5ab8f0;
--text:          #e8f4ff;
--text-secondary:#6b8fa8;
--text-muted:    #2a3d4f;
--font:          'JetBrains Mono', monospace;
```

## Key Architecture Decisions
- All LLM traffic routes through OpenClaw gateway (port 18789), not direct Anthropic SDK.
- Session memory is owned by OpenClaw; local SQLite (`data/jarvis.db`) is transcript archive only.
- WebSocket messages use a typed union — extend `WsMessage` type, never send untyped payloads.
- aiohttp, not FastAPI. The entrypoint is `python -m main`, not uvicorn.

## Further Docs
- Architecture & runtime agents: `docs/ARCHITECTURE.md`
- UI/UX design guidelines: `docs/DESIGN.md`
- Frontend design system: `docs/FRONTEND.md`
- Full implementation spec: `docs/PROJECT_DESCRIPTION.md`

