# Tailscale Remote Access Setup

Connect multiple devices to a JARVIS backend running on one host without
exposing any port to the public internet. Tailscale ACL is the authentication
boundary — there is no API-level token check in JARVIS today.

---

## Prerequisites

- Tailscale installed and `tailscale up` completed on every device that needs
  access. Download: https://tailscale.com/download
- All devices are in the same Tailscale account (tailnet).

---

## Enable on the JARVIS host

1. Add `JARVIS_REMOTE_ACCESS=true` to `.env` on the JARVIS host.
2. Restart the backend:
   ```bash
   PYTHONPATH=src .venv/bin/python -m main
   # or: docker-compose up --build
   ```
3. The log line `API bind host: '0.0.0.0' (source: env-remote-access ...)` confirms
   the backend is now listening on all interfaces, including the Tailscale interface.
4. From a peer device on the tailnet:
   ```bash
   curl http://<tailscale-host>:8766/health
   ```
   Replace `<tailscale-host>` with the Tailscale MagicDNS hostname or IP of the
   JARVIS machine (visible in `tailscale status`).

---

## MCP advertise host

JARVIS auto-detects the Tailscale hostname at startup so the MCP SSE URL
advertised to OpenClaw is reachable from remote devices.

Resolution order (highest priority first):

1. `JARVIS_MCP_ADVERTISE_HOST` env var — explicit override.
2. `mcp.advertise_host` in `config/config.yaml`.
3. `TAILSCALE_HOSTNAME` env var (fast path — set this when auto-detect is slow).
4. `tailscale status --json` subprocess (parses `Self.DNSName`; 2-second timeout;
   silent no-op if Tailscale is not installed).
5. `mcp.bind_host` fallback.

To override explicitly:
```bash
# .env
TAILSCALE_HOSTNAME=laptop-paps.tailnet.ts.net
# or
JARVIS_MCP_ADVERTISE_HOST=laptop-paps.tailnet.ts.net
```

---

## CORS

The frontend served from a remote device's browser will send an `Origin` header
that doesn't match `http://localhost:5173`. Add the Tailscale host origin to
`api.cors_origins` in `config/config.yaml`:

```yaml
api:
  cors_origins:
    - "http://localhost:5173"
    - "https://laptop-paps.tailnet.ts.net:5173"
    # Or use a wildcard (fnmatch-style) to cover any tailnet machine:
    - "https://*.tailnet.ts.net:5173"
```

Wildcard patterns use `fnmatch.fnmatchcase` — `*` matches any sequence of
characters within a segment.

> **Note:** the wildcard must include the port. `https://*.tailnet.ts.net`
> alone will not match `https://laptop.tailnet.ts.net:5173` — fnmatch globs
> do not span port separators. Always append `:5173` (or whatever port the
> Vite dev server uses) to the pattern.

---

## OpenClaw remote

When OpenClaw runs on a different machine than JARVIS, point the gateway URL
at the OpenClaw host's tailnet address:

```yaml
# config/config.yaml
openclaw:
  gateway_url: "http://100.84.x.y:18789"   # tailnet IP of the OpenClaw host
  gateway_port: 18789                        # same port as on the gateway host
```

You can also use the MagicDNS hostname: `http://openclaw-host.tailnet.ts.net:18789`.

---

## Multi-device ACL

In the Tailscale admin console (https://login.tailscale.com/admin/acls), restrict
access to JARVIS's port range to a tagged group of trusted devices only:

```json
{
  "acls": [
    {
      "action": "accept",
      "src":    ["tag:trusted-clients"],
      "dst":    ["tag:jarvis-host:8765-8767"]
    }
  ]
}
```

See the Tailscale ACL documentation:
https://tailscale.com/kb/1018/acls

---

## RPi migration

The `docker-compose.rpi.yml` already passes `JARVIS_REMOTE_ACCESS`,
`TAILSCALE_HOSTNAME`, and `JARVIS_MCP_ADVERTISE_HOST` through from the host
shell. On the RPi:

1. Set `JARVIS_REMOTE_ACCESS=true` in `.env`.
2. Run `docker-compose -f docker-compose.rpi.yml up --build`.
3. Tailscale must be installed and running on the RPi host (not inside the
   container); `network_mode: host` shares the Tailscale interface.

---

## Pointing a dev frontend at a remote backend

When developing on a Windows machine (or any secondary device) while the JARVIS
backend runs on the Linux laptop, both connected via the tailnet, you can tell
`npm run dev` to proxy all backend traffic to the remote host instead of
`127.0.0.1`. No changes to the source files are needed — the Vite dev-server
reads three env vars at startup.

Create (or edit) `frontend/.env.local` on the dev machine:

```
VITE_BACKEND_HOST=linux-laptop.tail-xxxxx.ts.net
VITE_BACKEND_HTTP_PORT=8766
VITE_BACKEND_WS_PORT=8765
```

Replace `tail-xxxxx` with your actual tailnet name (visible in `tailscale status`).

CORS on the backend side does not need to be updated for this flow — the
browser sees the request as coming from `http://localhost:5173`, which is
already in the default `cors_origins`.

Restart `npm run dev` after editing `.env.local` — Vite reads env at startup.

---

## Troubleshooting

- `tailscale status` shows the MagicDNS `DNSName` column for this machine.
- If `mcp.advertise_host` resolves to `127.0.0.1` after enabling Tailscale:
  1. Check backend logs for `Tailscale hostname auto-detected` or
     `MCP advertise host` log lines.
  2. Run `tailscale status --json` manually as the JARVIS OS user and confirm
     it exits 0 and the `Self.DNSName` field is populated.
  3. If `tailscale` is not in `PATH` for the JARVIS user, set
     `TAILSCALE_HOSTNAME` explicitly in `.env` as a workaround.
