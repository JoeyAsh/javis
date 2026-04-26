# Remote OpenClaw via Tailscale

This doc covers how to run the OpenClaw gateway on a separate machine (e.g. a Linux laptop) and connect JARVIS to it over Tailscale. No SSH tunnel required.

## Prerequisites

- [Tailscale](https://tailscale.com) installed and logged in on **both** machines.
- OpenClaw installed on the gateway host: `npm install -g openclaw`.
- OpenClaw installed locally (for the CLI token strategy): `npm install -g openclaw`.

## Step 1 — Bind the gateway on the tailnet

On the **Linux gateway host**, edit `~/.openclaw/openclaw.json`:

```json
{
  "gateway": {
    "bind": "tailscale"
  }
}
```

Alternatively pass `--bind tailscale` when starting the daemon. The gateway will listen on the Tailscale interface (e.g. `100.84.x.y:18789`) rather than loopback only.

Restart the gateway: `openclaw serve` (or `systemctl --user restart openclaw`).

## Step 2 — Configure the JARVIS Controller

Open the JARVIS Controller app on Windows. In the OpenClaw card:

1. Set **Mode** to `REMOTE`.
2. Paste the gateway's Tailscale IP into **OpenClaw Gateway URL**: `http://100.84.x.y:18789`.
3. Click **Save**.
4. Restart the JARVIS backend so it picks up the new URL.

The "Reachable" pill in the Controller confirms connectivity.

## Step 3 — Configure the Python backend

In `.env` (or `config/config.yaml`):

```
OPENCLAW_GATEWAY_URL=http://100.84.x.y:18789
```

Or set `openclaw.gateway_url` in `config/config.yaml` to the same Tailscale URL.

## Step 4 — Configure the local OpenClaw client

On the **Windows PC**, `~/.openclaw/openclaw.json` (or `%APPDATA%\.openclaw\openclaw.json`) must point to the remote gateway:

```json
{
  "gateway": {
    "mode": "remote",
    "remote": {
      "url": "ws://100.84.x.y:18789",
      "transport": "direct",
      "token": "<token from gateway host's openclaw.json>"
    }
  }
}
```

The shared token is found on the gateway host at `~/.openclaw/openclaw.json` → `gateway.auth.token`.

## Troubleshooting

| Symptom | Check |
|---|---|
| Controller shows "unreachable" | `ping 100.84.x.y` — is Tailscale up on both machines? |
| Gateway not on tailnet | `tailscale status` on gateway host — is it connected? |
| Port blocked | Check `openclaw.json` bind setting; confirm gateway is listening: `ss -tlnp \| grep 18789` |
| Token mismatch | Re-copy `gateway.auth.token` from the host's config to the client's `openclaw.json` |
| Wrong URL in backend | Check `OPENCLAW_GATEWAY_URL` in `.env` and `config/config.yaml` |
