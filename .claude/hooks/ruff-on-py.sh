#!/usr/bin/env bash
# JARVIS PostToolUse hook: lint Python files after edit/write.
# Surfaces ruff findings to the agent so violations get fixed before a reviewer cycle.

set -uo pipefail

if command -v jq >/dev/null 2>&1; then
    file_path=$(jq -r '.tool_input.file_path // empty' 2>/dev/null || true)
else
    payload=$(cat)
    file_path=$(echo "$payload" | grep -oE '"file_path"\s*:\s*"[^"]*"' | head -1 | sed -E 's/.*"file_path"\s*:\s*"([^"]*)".*/\1/')
fi

case "${file_path:-}" in
    *.py) ;;
    *) exit 0 ;;
esac

# Resolve venv-aware ruff (cross-platform).
if [ -x ".venv/Scripts/ruff.exe" ]; then
    RUFF=".venv/Scripts/ruff.exe"
elif [ -x ".venv/bin/ruff" ]; then
    RUFF=".venv/bin/ruff"
elif command -v ruff >/dev/null 2>&1; then
    RUFF="ruff"
else
    # ruff not installed — silently skip rather than spamming.
    exit 0
fi

# Run ruff; non-blocking — just emit findings.
output=$("$RUFF" check --no-fix "$file_path" 2>&1) && rc=0 || rc=$?

if [ "$rc" -ne 0 ] && [ -n "$output" ]; then
    {
        echo "ruff found issues in $file_path:"
        echo "$output"
        echo "(non-blocking; please fix before passing to reviewer)"
    } >&2
fi

exit 0
