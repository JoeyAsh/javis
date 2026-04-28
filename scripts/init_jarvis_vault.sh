#!/usr/bin/env bash
# init_jarvis_vault.sh — Idempotent initialisation of the JARVIS knowledge vault.
#
# Calls `openclaw wiki init` to scaffold the vault directory, then verifies via
# `openclaw wiki status --json`.  Re-running when already initialised is a no-op.
#
# Environment variables:
#   JARVIS_VAULT_PATH   Override the default vault location (default: ~/Obsidian/jarvis-vault)
#
# Exit codes:
#   0   Vault is initialised (new or pre-existing)
#   1   Pre-flight check failed (memory-wiki plugin not active) — see instructions
#   2   Initialisation failed

set -euo pipefail

# ---------------------------------------------------------------------------
# Resolve vault path
# ---------------------------------------------------------------------------

DEFAULT_VAULT_PATH="${HOME}/Obsidian/jarvis-vault"
RAW_PATH="${JARVIS_VAULT_PATH:-${DEFAULT_VAULT_PATH}}"

# Expand a leading ~ explicitly when the value came from an env var.
case "${RAW_PATH}" in
  "~/"*)  VAULT_PATH="${HOME}/${RAW_PATH#~/}" ;;
  "~")    VAULT_PATH="${HOME}" ;;
  *)      VAULT_PATH="${RAW_PATH}" ;;
esac

printf '\n[init_jarvis_vault] vault path: %s\n' "${VAULT_PATH}"

# ---------------------------------------------------------------------------
# Helper: parse a JSON field with Python (no jq dependency required)
# ---------------------------------------------------------------------------

_json_field() {
  local json="$1"
  local field="$2"
  python3 -c "
import json, sys
try:
    data = json.loads('''${json}''')
    val = data.get('${field}')
    print(str(val).lower() if isinstance(val, bool) else (val or ''))
except Exception as e:
    sys.exit(0)
"
}

# ---------------------------------------------------------------------------
# Pre-flight: verify memory-wiki plugin is active
# ---------------------------------------------------------------------------

WIKI_STATUS_JSON=""
if ! WIKI_STATUS_JSON=$(openclaw wiki status --json 2>&1); then
  printf '\n[init_jarvis_vault] ERROR: `openclaw wiki status --json` failed.\n'
  printf '\nThe memory-wiki plugin is likely not enabled in your OpenClaw config.\n'
  printf 'Run the following commands to activate it, then re-run this script:\n\n'
  printf '  openclaw config set plugins.entries.memory-wiki.config.vaultMode '"'"'"bridge"'"'"'\n'
  printf '  openclaw config set plugins.entries.memory-wiki.config.vault.path '"'"'"~/Obsidian/jarvis-vault"'"'"'\n'
  printf '  openclaw config set plugins.entries.memory-wiki.config.vault.renderMode '"'"'"obsidian"'"'"'\n'
  printf '  openclaw config set plugins.entries.memory-wiki.config.obsidian.enabled true\n'
  printf '  openclaw config set plugins.entries.memory-wiki.config.bridge.enabled true\n'
  printf '\nThen restart the OpenClaw gateway so the plugin loads:\n'
  printf '  openclaw daemon restart\n'
  printf '  # or: systemctl --user restart openclaw-gateway.service\n\n'
  exit 1
fi

# Detect "unknown command" output in case openclaw does not recognise `wiki` at all.
if printf '%s' "${WIKI_STATUS_JSON}" | grep -qi "unknown command"; then
  printf '\n[init_jarvis_vault] ERROR: `openclaw wiki` command not found.\n'
  printf 'The memory-wiki plugin is not enabled. Follow the activation steps below:\n\n'
  printf '  openclaw config set plugins.entries.memory-wiki.config.vaultMode '"'"'"bridge"'"'"'\n'
  printf '  openclaw config set plugins.entries.memory-wiki.config.vault.path '"'"'"~/Obsidian/jarvis-vault"'"'"'\n'
  printf '  openclaw config set plugins.entries.memory-wiki.config.vault.renderMode '"'"'"obsidian"'"'"'\n'
  printf '  openclaw config set plugins.entries.memory-wiki.config.obsidian.enabled true\n'
  printf '  openclaw config set plugins.entries.memory-wiki.config.bridge.enabled true\n'
  printf '  openclaw daemon restart\n\n'
  exit 1
fi

# ---------------------------------------------------------------------------
# Idempotency check: already initialised?
# ---------------------------------------------------------------------------

VAULT_EXISTS=$(_json_field "${WIKI_STATUS_JSON}" "vaultExists" 2>/dev/null || printf "false")
VAULT_PATH_IN_STATUS=$(_json_field "${WIKI_STATUS_JSON}" "vaultPath" 2>/dev/null || printf "")

if [ "${VAULT_EXISTS}" = "true" ]; then
  printf '[init_jarvis_vault] Vault already initialised at: %s\n' "${VAULT_PATH_IN_STATUS:-${VAULT_PATH}}"
  printf '[init_jarvis_vault] Nothing to do — exiting 0.\n\n'
  exit 0
fi

# ---------------------------------------------------------------------------
# Configure vault path in OpenClaw config (idempotent)
# ---------------------------------------------------------------------------

printf '[init_jarvis_vault] Configuring vault path in OpenClaw...\n'
openclaw config set plugins.entries.memory-wiki.config.vault.path "\"${VAULT_PATH}\"" >/dev/null || {
  printf '[init_jarvis_vault] WARNING: Could not set vault path in config — continuing anyway.\n'
}

# ---------------------------------------------------------------------------
# Create the directory and initialise the vault layout
# ---------------------------------------------------------------------------

printf '[init_jarvis_vault] Creating vault directory: %s\n' "${VAULT_PATH}"
mkdir -p "${VAULT_PATH}"

printf '[init_jarvis_vault] Running: openclaw wiki init\n'
if ! openclaw wiki init; then
  printf '\n[init_jarvis_vault] ERROR: `openclaw wiki init` failed (exit %d).\n' "$?"
  printf 'Check the output above for details.\n\n'
  exit 2
fi

# ---------------------------------------------------------------------------
# Verify: re-read status and assert vaultExists=true
# ---------------------------------------------------------------------------

printf '[init_jarvis_vault] Verifying initialisation...\n'
VERIFY_JSON=""
if ! VERIFY_JSON=$(openclaw wiki status --json 2>&1); then
  printf '[init_jarvis_vault] ERROR: post-init status check failed.\n'
  exit 2
fi

VERIFY_EXISTS=$(_json_field "${VERIFY_JSON}" "vaultExists" 2>/dev/null || printf "false")
VERIFY_PATH=$(_json_field "${VERIFY_JSON}" "vaultPath" 2>/dev/null || printf "")

if [ "${VERIFY_EXISTS}" != "true" ]; then
  printf '\n[init_jarvis_vault] ERROR: vault init appeared to succeed but status still reports\n'
  printf '  vaultExists=false. Manual investigation required.\n\n'
  exit 2
fi

printf '\n[init_jarvis_vault] Vault successfully initialised.\n'
printf '  path: %s\n\n' "${VERIFY_PATH:-${VAULT_PATH}}"
exit 0
