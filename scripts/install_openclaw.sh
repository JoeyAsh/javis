#!/bin/bash
# Install OpenClaw for JARVIS agent-runtime backbone
#
# Prerequisites:
#   - Node.js 24+ (or 22.16+)
#   - npm
#
# Usage:
#   ./scripts/install_openclaw.sh
#
# This script:
#   1. Installs OpenClaw globally via npm
#   2. Runs onboarding to create ~/.openclaw/ directory
#   3. Optionally installs the daemon (systemd/launchd)
#   4. Deploys JARVIS SOUL.md persona to OpenClaw workspace

set -e

echo "=== JARVIS OpenClaw Installation ==="

# Check Node.js version
if ! command -v node &> /dev/null; then
    echo "ERROR: Node.js is not installed."
    echo "Please install Node.js 24+ (or 22.16+) before running this script."
    exit 1
fi

NODE_VERSION=$(node --version | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$NODE_VERSION" -lt 22 ]; then
    echo "WARNING: Node.js version may be too old (found v$(node --version))."
    echo "OpenClaw requires Node.js 24+ (or 22.16+)."
fi

echo "Node.js version: $(node --version)"

# Check if OpenClaw is already installed
if command -v openclaw &> /dev/null; then
    CURRENT_VERSION=$(openclaw --version 2>/dev/null || echo "unknown")
    echo "OpenClaw is already installed (version: $CURRENT_VERSION)"
    read -p "Do you want to update to the latest version? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Skipping OpenClaw installation."
    else
        echo "Updating OpenClaw..."
        npm install -g openclaw@latest
    fi
else
    echo "Installing OpenClaw..."
    npm install -g openclaw@latest
fi

# Verify installation
if ! command -v openclaw &> /dev/null; then
    echo "ERROR: OpenClaw installation failed."
    exit 1
fi
echo "OpenClaw installed: $(openclaw --version)"

# Run onboarding (creates ~/.openclaw/ directory structure)
if [ ! -d "$HOME/.openclaw" ]; then
    echo "Running OpenClaw onboarding..."
    openclaw onboard
else
    echo "OpenClaw configuration already exists at ~/.openclaw"
fi

# Ask about daemon installation
echo ""
read -p "Install OpenClaw daemon (systemd/launchd)? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Installing OpenClaw daemon..."
    openclaw onboard --install-daemon
    echo "Daemon installed."
else
    echo "Skipping daemon installation."
    echo "You can install it later with: openclaw onboard --install-daemon"
fi

# Deploy JARVIS SOUL.md
SOUL_SOURCE="$(dirname "$0")/../config/SOUL.md"
SOUL_DEST="$HOME/.openclaw/workspace/SOUL.md"

if [ -f "$SOUL_SOURCE" ]; then
    mkdir -p "$HOME/.openclaw/workspace"

    if [ -f "$SOUL_DEST" ]; then
        echo "SOUL.md already exists at $SOUL_DEST"
        read -p "Overwrite with JARVIS persona? [y/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            cp "$SOUL_SOURCE" "$SOUL_DEST"
            echo "JARVIS persona deployed to $SOUL_DEST"
        fi
    else
        cp "$SOUL_SOURCE" "$SOUL_DEST"
        echo "JARVIS persona deployed to $SOUL_DEST"
    fi
else
    echo "WARNING: SOUL.md not found at $SOUL_SOURCE"
    echo "JARVIS persona not deployed. Create config/SOUL.md and run this script again."
fi

# --------------------------------------------------------------------------
# Config hardening — every key below caused concrete bugs during JARVIS dev;
# the `openclaw config set` commands are idempotent, so re-runs are safe.
# --------------------------------------------------------------------------

echo ""
echo "=== Hardening OpenClaw config for JARVIS ==="

# 1. Gateway must run in local mode, otherwise the daemon exits with code 78
#    at startup ("gateway.mode is unset; gateway start will be blocked").
echo "  - gateway.mode = local"
openclaw config set gateway.mode local >/dev/null

# 2. Default agent model. Without this the gateway falls through to its
#    internal default (openai/gpt-5.4) and every turn fails with
#    FailoverError because no OpenAI key is configured.
DESIRED_MODEL="claude-cli/claude-opus-4-7"
echo "  - agents.defaults.model = $DESIRED_MODEL"
openclaw config set agents.defaults.model "$DESIRED_MODEL" >/dev/null

# 3. Disable semantic memory search (needs an embedding provider we don't
#    configure here). Doctor otherwise prints noisy "no embedding provider
#    ready" warnings on every run.
echo "  - agents.defaults.memorySearch.enabled = false"
openclaw config set agents.defaults.memorySearch.enabled false >/dev/null

# Restart the gateway so the new config takes effect immediately (no-op
# if the daemon wasn't running).
if systemctl --user is-active --quiet openclaw-gateway.service 2>/dev/null; then
    echo "  - restarting openclaw-gateway.service"
    systemctl --user restart openclaw-gateway.service || true
fi

# Run diagnostics
echo ""
echo "=== Running OpenClaw Diagnostics ==="
openclaw doctor || echo "WARNING: Some diagnostics failed. Check the output above."

echo ""
echo "=== Installation Complete ==="
echo ""
echo "Next steps:"
echo "  1. Configure API keys in ~/.openclaw/openclaw.json or ~/.env"
echo "  2. Start the daemon: openclaw daemon start"
echo "  3. Verify health: openclaw doctor"
echo "  4. Start JARVIS: PYTHONPATH=src uvicorn main:app --host 0.0.0.0 --port 8000"
echo ""
