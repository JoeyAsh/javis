---
name: jarvis-run-dev
description: Starts the JARVIS dev stack — backend (aiohttp :8765/:8766) and frontend (Vite :5173) — with port-collision checks and health-polling. Handles Windows/Unix venv path differences.
---

# JARVIS dev-stack start

Invoke this skill when you need JARVIS running locally. It starts both the aiohttp backend and the Vite frontend in the background, checks port availability first, and polls for healthy responses before returning.

Run each step in order. If any step fails, abort with the error — don't start downstream processes on a broken upstream.

---

## Step 1 — Detect OS

```bash
case "$(uname -s 2>/dev/null || echo unknown)" in
    Linux*|Darwin*|CYGWIN*|MINGW*|MSYS*) OS="unix" ;;
    *) OS="windows" ;;
esac
echo "OS detected: $OS"
```

Windows Git Bash / MSYS reports `MINGW64_NT-*` — treat as unix-style paths but backend venv uses `Scripts/` not `bin/`.

## Step 2 — Resolve Python venv path

```bash
if [ -f ".venv/Scripts/python.exe" ]; then
    PYTHON=".venv/Scripts/python.exe"
elif [ -f ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
else
    echo "ERROR: no Python venv found at .venv/Scripts/python.exe or .venv/bin/python" >&2
    exit 1
fi
echo "Python: $PYTHON"
```

## Step 3 — Port-collision check

```bash
for port in 8765 8766 5173; do
    if netstat -ano 2>/dev/null | grep -qE ":$port\s.*LISTEN|:$port\s.*ABH"; then
        pid=$(netstat -ano | grep -E ":$port\s" | head -1 | awk '{print $NF}')
        echo "Port $port already in use (PID $pid)"
        echo "  Options: kill the existing process, or skip startup if it's already the process you wanted."
        PORT_BUSY_$port=1
    else
        echo "Port $port free"
    fi
done
```

On Unix, `lsof -ti:$port` is the common alternative. On Windows, `netstat -ano | findstr :$port` works in cmd; `netstat -ano | grep` works in Git Bash / MSYS.

If any port is busy, **ask the user** before killing — don't auto-kill.

## Step 4 — Start backend (if port 8766 is free)

```bash
PYTHONPATH=src "$PYTHON" -m main > .tmp_backend.log 2>&1 &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"
```

## Step 5 — Wait for `/health` (up to 15 s)

```bash
for i in $(seq 1 15); do
    if curl -sf http://localhost:8766/health >/dev/null 2>&1; then
        echo "Backend healthy after ${i}s"
        break
    fi
    sleep 1
    if [ "$i" = "15" ]; then
        echo "ERROR: backend did not become healthy within 15s. Tail of .tmp_backend.log:" >&2
        tail -30 .tmp_backend.log >&2
        exit 1
    fi
done
```

## Step 6 — Start frontend (if port 5173 is free)

```bash
(cd frontend && npm run dev > ../.tmp_frontend.log 2>&1 &)
FRONTEND_PID=$!
echo "Frontend PID: $FRONTEND_PID"
```

## Step 7 — Wait for Vite dev server (up to 20 s)

```bash
for i in $(seq 1 20); do
    if curl -sf -o /dev/null -w "%{http_code}" http://localhost:5173/ 2>/dev/null | grep -q '^200$'; then
        echo "Frontend ready after ${i}s"
        break
    fi
    sleep 1
    if [ "$i" = "20" ]; then
        echo "ERROR: frontend did not serve 200 within 20s. Tail of .tmp_frontend.log:" >&2
        tail -30 .tmp_frontend.log >&2
        exit 1
    fi
done
```

## Step 8 — Summary

```bash
echo ""
echo "JARVIS running:"
echo "  Backend:  PID $BACKEND_PID  →  ws://localhost:8765/ws  +  http://localhost:8766/health"
echo "  Frontend: PID $FRONTEND_PID  →  http://localhost:5173"
echo ""
echo "Logs: .tmp_backend.log and .tmp_frontend.log"
echo "Stop: kill $BACKEND_PID $FRONTEND_PID"
```

---

## Notes

- The backend takes ~10 s to load the Whisper STT model on cold start. The 15 s health-poll window accommodates this.
- The frontend Vite dev server typically starts in 1–2 s — the 20 s window is a safety margin.
- On RPi deployments, the frontend is served from the developer PC and connects to `ws://<rpi-ip>:8765`. This skill assumes localhost dev.
- If `docker-compose.yml` is preferred, substitute steps 4–7 with `docker-compose up --build` and a single poll against `:5173`.
- The `.tmp_backend.log` and `.tmp_frontend.log` files are gitignored by the project's `.gitignore` (`.tmp*`). Safe to leave them around for debugging.
