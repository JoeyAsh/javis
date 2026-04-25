---
name: jarvis-tests-run
description: Run the full JARVIS test suite — pytest (Python backend) + vitest (frontend) — and emit a unified summary. Cross-platform venv resolution included.
---

# JARVIS tests-run skill

## When to use

After a dev agent has produced or modified files and the tester has produced tests. The orchestrator runs this skill to get a single verdict before invoking the reviewer.

## Inputs

- Optional: `<scope>` — `backend`, `frontend`, or `all` (default `all`).
- Optional: `<pytest-args>` — extra args passed to pytest (e.g. `tests/test_audio_stt.py -v`).

## Steps

```bash
# 1. Resolve Python venv (cross-platform — same logic as jarvis-run-dev)
if [ -f ".venv/Scripts/python.exe" ]; then
    PYTHON=".venv/Scripts/python.exe"
elif [ -f ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
else
    echo "ERROR: no Python venv found at .venv/Scripts/python.exe or .venv/bin/python" >&2
    exit 1
fi

# 2. Backend (if scope=all or backend)
if [ "<scope>" != "frontend" ]; then
    echo "=== pytest ==="
    PYTHONPATH=src "$PYTHON" -m pytest <pytest-args> 2>&1 | tee .tmp_pytest.log
    BACKEND_RC=${PIPESTATUS[0]}
fi

# 3. Frontend (if scope=all or frontend)
if [ "<scope>" != "backend" ]; then
    echo "=== vitest ==="
    (cd frontend && npm run test -- --run 2>&1) | tee .tmp_vitest.log
    FRONTEND_RC=${PIPESTATUS[0]}
fi

# 4. Summary
echo ""
echo "=== Summary ==="
[ -n "$BACKEND_RC" ]  && echo "Backend  pytest:  $([ $BACKEND_RC  -eq 0 ] && echo PASS || echo FAIL)"
[ -n "$FRONTEND_RC" ] && echo "Frontend vitest:  $([ $FRONTEND_RC -eq 0 ] && echo PASS || echo FAIL)"

# 5. Exit with combined status
exit $(( ${BACKEND_RC:-0} | ${FRONTEND_RC:-0} ))
```

## Notes

- `--run` on vitest forces non-watch mode.
- `.tmp_pytest.log` and `.tmp_vitest.log` are gitignored by `.tmp*`. Reviewer can grep them for failure context.
- On `FAIL`, the orchestrator should NOT proceed to `reviewer` — fix the failing tests first via the relevant dev agent.
