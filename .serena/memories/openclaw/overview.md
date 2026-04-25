# OpenClaw — Overview

Local clone: `D:/Repos/openclaw` (npm package `openclaw`, monorepo, TypeScript).
Runtime state: `~/.openclaw/` (config `openclaw.json`, identity, workspace, skills).

## What it is
Personal, single-user AI assistant control plane. JARVIS uses it as the **agent runtime** while owning the voice pipeline + HUD itself.

## Core concepts
- **Gateway** — local-first daemon (default `:18789`) that hosts sessions, channels, tools, agents. Auth via Ed25519 device key + shared token. Protocol v3 over WS.
- **Sessions** — keyed conversations with their own memory; default key for JARVIS is `agent:main:explicit:jarvis-main`.
- **Agents** — model-bound personas; routed per channel/peer/workspace. Models specified as `<provider>/<model-id>` (e.g. `claude-cli/claude-opus-4-7`, `anthropic/claude-sonnet-4-6`).
- **Channels** (multi-channel inbox): WhatsApp, Telegram, Slack, Discord, Google Chat, Signal, iMessage/BlueBubbles, IRC, MS Teams, Matrix, Feishu, LINE, Mattermost, Nextcloud Talk, Nostr, Synology Chat, Tlon, Twitch, Zalo, WeChat, QQ, WebChat, plus macOS / iOS / Android nodes.
- **Skills** — `~/.openclaw/workspace/skills/<skill>/SKILL.md`; registry at ClawHub.
- **Tools** (first-class) — browser, canvas, nodes, cron, sessions (`sessions_list`/`history`/`send`/`spawn`), shell (`bash`/`process`/`read`/`write`/`edit`).
- **Automation** — cron-jobs, webhooks, Gmail Pub/Sub, standing orders, hooks, taskflow/clawflow.
- **Live Canvas** (A2UI) — agent-driven visual workspace, primarily macOS app + iOS/Android nodes.
- **Voice Wake / Talk Mode** — wake words on macOS/iOS, continuous voice on Android.
- **Sandboxing** — Docker (default) / SSH / OpenShell backends for non-`main` sessions.

## CLI surface (selected)
- `openclaw onboard --install-daemon` — guided setup; installs systemd/launchd unit.
- `openclaw gateway --port 18789` — run gateway in foreground.
- `openclaw doctor` — diagnostics (DM policy, channels, auth, daemon).
- `openclaw agent --message "..." --thinking high|medium|low|off|minimal|xhigh --session-id <id> --json` — one-shot agent query (returns run envelope: `result.payloads`, `result.meta.finalAssistantVisibleText`).
- `openclaw message send --channel <ch> --to <id> --message "..."` — send via any channel.
- `openclaw sessions list|history|reset|send|spawn` — session ops.
- `openclaw cron / hooks / flows / approvals / pairing / channels / nodes / devices / skills / mcp / memory / sandbox / secrets`.

## How JARVIS uses it (current)
- Persistent WS streaming client at `src/integrations/openclaw/ws_client.py` (Ed25519 auth, auto-reconnect, fan-out per `runId`).
- CLI fallback subprocess at `src/integrations/openclaw/client.py` (also handles Windows .cmd shim by spawning `node openclaw.mjs` directly).
- Gateway URL configured in `config/config.yaml` under `openclaw:` (default `http://192.168.1.121:18789`).
- Session ID `jarvis-main`, thinking level `medium`, model `claude-cli/claude-opus-4-7`.
- Health checks via plain HTTP GET on the root URL (NOT `openclaw doctor`, too slow).

## Key URLs
- Source: https://github.com/openclaw/openclaw
- Docs: https://docs.openclaw.ai
- Skills registry: https://clawhub.ai
- DeepWiki: https://deepwiki.com/openclaw/openclaw
