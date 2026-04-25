#!/usr/bin/env bash
# JARVIS Stop hook: surface git status + remind about orchestrator-only policy.

set -uo pipefail

# git status (short form), trim to a sane number of lines.
status=$(git status --short 2>/dev/null | head -40)

if [ -z "$status" ]; then
    exit 0
fi

{
    echo "── Stop hook ── git status (top 40):"
    echo "$status"
    echo ""
    echo "Reminder: per CLAUDE.md, Opus-Orchestrator delegiert Schreib-/Edit-Aktionen an Sonnet-Subagents. Falls die obigen Änderungen direkt vom Orchestrator stammen, ist das ein Policy-Verstoß — Subagent erneut aufrufen statt selbst nachbessern."
} >&2

exit 0
