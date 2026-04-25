#!/usr/bin/env bash
# JARVIS PreToolUse hook: forbid edits to the frozen orb engine.
# CLAUDE.md declares frontend/src/ui/orb/orbEngine.ts as a black box; this hook enforces it.

set -euo pipefail

# Read JSON payload from stdin; tolerate jq absence on Windows minimal Git Bash setups.
if command -v jq >/dev/null 2>&1; then
    file_path=$(jq -r '.tool_input.file_path // empty' 2>/dev/null || true)
else
    payload=$(cat)
    file_path=$(echo "$payload" | grep -oE '"file_path"\s*:\s*"[^"]*"' | head -1 | sed -E 's/.*"file_path"\s*:\s*"([^"]*)".*/\1/')
fi

# Normalize separators for matching.
norm=$(echo "${file_path:-}" | tr '\\' '/')

case "$norm" in
    *frontend/src/ui/orb/orbEngine.ts|*frontend/src/ui/orb/orbEngine.tsx)
        echo "BLOCKED: $file_path is the frozen Three.js orb engine. CLAUDE.md forbids modifications. Route the desired behavior through orb.setState / setAnalyser / destroy at the call site instead." >&2
        exit 2
        ;;
esac

exit 0
