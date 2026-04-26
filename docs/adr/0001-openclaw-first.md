# ADR-0001: OpenClaw-First — Single Source of Intelligence + Local MCP Servers for Coverage Gaps

## Status

**Accepted** — 2026-04-26

---

## Context

### The duplication problem

JARVIS has grown two independent integration stacks for overlapping capabilities. As of 2026-04-26:

| Capability | JARVIS implementation | OpenClaw equivalent |
|---|---|---|
| Gmail, Calendar, Drive | `src/integrations/google/` (OAuth2, token cache at `~/.jarvis/google_token.json`, polling loop) | `gog` skill + `google` extension |
| Web search | `src/actions/web_search.py` (DuckDuckGo via `duckduckgo-search`) | `brave`, `duckduckgo`, `exa`, `tavily`, `searxng`, `firecrawl` extensions |

Both stacks hold independent auth tokens, run their own polling loops, and are invoked by different code paths depending on whether the intent landed in JARVIS's action router or in the OpenClaw agent. This is classic accidental duplication — both implementations were written by different agents in different sessions without a cross-check.

### The concrete failure mode this ADR responds to

On 2026-04-26 at approximately 02:11–02:14 (see PR #67 backend logs), the user asked JARVIS to read his unread mail. The request was routed through the OpenClaw agent. The agent had no awareness that JARVIS was already authenticated with a cached Gmail token and returned:

```
I need access to your Google account first. Run: gog auth add ...
```

This was a hallucination in the operational sense: the agent recommended an unnecessary auth step because the Google credential lived outside OpenClaw's token store. The JARVIS-side integration and the OpenClaw-side integration are invisible to each other. The user's response was unambiguous: "alles was OpenClaw kann und was ich an features will möchte ich dort nutzen und nicht selber entwickeln" — single source of truth.

### What OpenClaw does cover

OpenClaw (local clone at `D:/Repos/openclaw/`, runtime under `~/.openclaw/`) is a self-hosted agent runtime with:
- A skill layer (`skills/` directory): composable, model-callable tools.
- An extension layer (`extensions/` directory): persistent integrations with external services, including full OAuth lifecycle management. Relevant existing extensions: `google` (Gmail + Calendar + Drive), `brave`, `duckduckgo`, `exa`, `tavily`, `searxng`, `firecrawl`, and others.
- Native MCP support (`openclaw mcp` CLI): OpenClaw can both act as an MCP client (calling external MCP servers) and expose its own tools via MCP.
- A WebSocket gateway that JARVIS connects to over Tailscale.

### What OpenClaw does NOT cover

No extension or skill exists for:
- **Spotify** — playback control, now-playing state, playlist management.
- **GitHub** — PR status, issue lists, review comments. (`github-copilot` extension is an LLM provider adapter, not a GitHub REST API integration.)
- **GitLab** — CI pipeline status, MR management.
- **Home Assistant** — entity state reads, service calls (lights, sensors, presence).
- **PC control** — window focus, app launch, volume, display control. By nature device-specific.
- **System metrics** — CPU, RAM, GPU, thermals, disk. Also device-specific.

### Deployment topology

JARVIS runs on multiple devices: a Windows workstation, a macOS laptop, a Linux desktop, and a Raspberry Pi 5 (planned). OpenClaw runs on a single Linux laptop. They communicate over WebSocket through Tailscale. OpenClaw cannot call device-local APIs (Spotify client, hardware metrics, window manager) because it runs on a different host.

---

## Decision

This ADR establishes a two-part policy.

### Part 1 — OpenClaw-First

For any capability covered by an OpenClaw skill or extension, JARVIS **shall not maintain a parallel implementation**. Concretely:

1. `src/integrations/google/` is deprecated and will be removed. Gmail, Calendar, and Drive calls are routed through the `gog` OpenClaw skill. OpenClaw owns the OAuth token; JARVIS's own token cache (`~/.jarvis/google_token.json`) is retired.
2. `src/actions/web_search.py` is deprecated and will be removed. Web search is dispatched to whichever OpenClaw search extension is configured.
3. Before any new feature is implemented in the JARVIS backend, the OpenClaw extension catalogue (`D:/Repos/openclaw/extensions/`) must be checked. If an extension exists, JARVIS shall delegate, not implement.

This applies permanently, not just to the current migration batch.

### Part 2 — Local MCP Server in the JARVIS Backend for Coverage Gaps

Capabilities that OpenClaw lacks (Spotify, GitHub, GitLab, Home Assistant, PC control, system metrics) will be exposed via the **Model Context Protocol** (MCP). OpenClaw supports MCP natively via `openclaw mcp` CLI, allowing the OpenClaw agent to call MCP-exposed tools as first-class actions.

The MCP server runs **inside the JARVIS backend process on each device** — on the loopback interface, not exposed to the network. OpenClaw calls those MCP tools through the existing WS channel, which is extended to carry MCP tool-call messages. When the user's voice session is active on a given device, OpenClaw's agent automatically uses the MCP tools exposed by that device's JARVIS backend.

#### Data flow

```
[Linux laptop]                            [Win/macOS/RPi running JARVIS]
┌────────────────┐                        ┌─────────────────────────────┐
│ OpenClaw       │     WS over Tailscale  │ JARVIS backend              │
│ Gateway        │◄──────────────────────►│  - Voice pipeline           │
│                │                        │  - HUD WS server            │
│                │      MCP tool call     │  - MCP server (loopback)    │
│                │ ──────────────────────►│      [spotify, github,      │
│                │                        │       gitlab, ha, pc,       │
│                │ ◄────────────────────── │       system_metrics]       │
│                │       MCP result        │                             │
└────────────────┘                        └─────────────────────────────┘
```

#### Why local MCP per device, not a centralised server

- **Device-specific tools are non-negotiable local**: `system_metrics` reads `/proc` or Windows PDH on the local host; `pc_control` calls the local window manager or system audio; `spotify` controls the Spotify client running on the same machine. These cannot be hosted on a different device.
- **Device-independent tools (HA, GitHub, GitLab)** could in principle live on a centralised host. However, for a single-user multi-device setup, placing them in the same MCP layer as device-specific tools eliminates a separate deployment unit. Auth tokens (GitHub PAT, HA long-lived token) are replicated to each device via `.env` — acceptable operational cost for a personal system.
- **Session locality**: OpenClaw's active WS session always points at whichever JARVIS backend is the current voice client. Placing MCP on that same process means OpenClaw naturally calls the right device without any routing logic.
- **Blast radius**: if the MCP server on a device fails, it only affects that device's session, not all JARVIS installations.

---

## Consequences

### Positive

- **One code path per external service.** The "did OpenClaw handle this, or did JARVIS?" ambiguity disappears. Debugging and logging collapse to a single path.
- **OpenClaw agent has full situational awareness.** The `gog auth` class of hallucination is impossible once Google credentials live exclusively in OpenClaw's profile store.
- **Backend codebase shrinks.** `src/integrations/google/` (multiple files, OAuth2 refresh loop, token cache) and `src/actions/web_search.py` are removed with no replacement in the JARVIS backend.
- **No new parallel-implementation drift.** The "check OpenClaw catalogue first" rule makes this structural, not a one-time cleanup.
- **HUD panels stay snappy.** Polling and streaming logic for UI state (now-playing, upcoming calendar event, unread count) remain in the JARVIS backend. Only the actual data-fetch RPC is delegated to OpenClaw or the MCP layer. There is no additional round-trip for the HUD render path beyond what was already there.
- **MCP is the extension point for new hardware/device capabilities.** Adding a new device-local tool means writing one MCP tool handler in Python; no changes required in OpenClaw.

### Negative

- **OpenClaw must be reachable for every voice turn that requires external data.** A Tailscale outage or OpenClaw crash degrades voice capability beyond voice-only turns. Mitigated by: Tailscale's mesh reliability, the existing WS reconnect logic in `src/integrations/openclaw/`, and the existing CLI subprocess fallback.
- **MCP server is an additional service the backend hosts.** One more thing to start, monitor, and restart. Mitigated by hosting it in-process inside the existing aiohttp server rather than as a separate process.
- **Auth migration for existing installations.** Google tokens currently in `~/.jarvis/google_token.json` must be re-issued through `gog auth add`. This is a one-time manual step per user (currently one user).
- **MCP transport over WS is an early protocol surface.** The MCP spec is stable but OpenClaw's WS MCP bridge may have edge cases. Integration tests must cover tool-call/result round-trips.

### Acceptable risks

- **Latency on Google and web-search calls traverses Tailscale.** For polling intervals (60–120 s) the added RTT (typically <10 ms on LAN Tailscale) is irrelevant. For synchronous voice responses, OpenClaw is already on the critical path, so this adds no new hop.
- **Single point of failure (OpenClaw) for intelligence routing.** Accepted; JARVIS is a personal assistant with one user, not a production service with an SLA.

---

## Migration Plan

Migration executes in four phases. Each phase is a separate PR.

### Phase 1 — Google → OpenClaw `gog` skill

Remove `src/integrations/google/`. Replace all call sites with a thin `OpenClawClient.call_skill("gog", ...)` wrapper. Retire `~/.jarvis/google_token.json`. Update affected features: mail polling, calendar briefing, drive search.

### Phase 2 — Web search → OpenClaw search extensions

Remove `src/actions/web_search.py`. Replace with `OpenClawClient.call_skill("search", ...)`. Determine extension priority order (brave → exa → duckduckgo) in `config/config.yaml` so it remains user-configurable without code changes.

### Phase 3 — MCP server bootstrap + gap tools

Implement `src/mcp/server.py` using the `mcp` Python SDK. Register tools: `spotify_control`, `spotify_now_playing`, `github_pr_list`, `github_issue_list`, `gitlab_pipeline_status`, `ha_entity_get`, `ha_service_call`, `pc_control`, `system_metrics`. Wire the MCP server startup into `main.py` alongside the existing aiohttp server. Register the JARVIS MCP endpoint in OpenClaw's config (`~/.openclaw/mcp.json`).

### Phase 4 — Voice pipeline intent routing

Audit the voice pipeline intent classifier. Non-trivial intents (anything beyond direct TTS playback or UI state reads) must be dispatched to OpenClaw rather than handled in local action handlers. Local action handlers that were wrappers around now-removed integrations are deleted.

---

## Alternatives Considered

### Pure OpenClaw extensions in TypeScript for the gaps

Write a `spotify` extension, a `github` extension, etc. upstream in OpenClaw's extension format. Advantage: single runtime, no MCP transport. Rejected because: (a) it requires contributing TypeScript code to a separate repo and keeping it in sync; (b) device-specific tools like `system_metrics` and `pc_control` cannot be reasonably implemented as a static extension — they would need to know which device to call, bringing back the routing problem; (c) timeline cost is high for what MCP already solves cleanly.

### Centralised MCP server on the OpenClaw host (Linux laptop)

Run one MCP server on the same machine as OpenClaw rather than one per JARVIS device. Advantage: simpler process count per device. Rejected because: (a) device-specific tools (`system_metrics`, `pc_control`, `spotify`) must run on the device where the user is; (b) routing those calls from the OpenClaw host back to the active JARVIS device reintroduces the same topology problem we are solving; (c) for device-independent tools (HA, GitHub), the "simpler model" advantage is marginal and does not outweigh (a) and (b).

### Status quo — maintain parallel JARVIS implementations

Keep `src/integrations/google/` and `src/actions/web_search.py` and expand them. Rejected per explicit user direction, and validated by the production bug: the OpenClaw agent recommended unnecessary re-authentication because it was blind to the JARVIS-side token. Parallel implementations create invisible split-brain state.

---

## References

- OpenClaw extensions directory: `D:/Repos/openclaw/extensions/`
- OpenClaw MCP CLI reference: `D:/Repos/openclaw/docs/cli/mcp.md`
- MCP specification: https://modelcontextprotocol.io
- The triggering bug: PR #67 backend logs, timestamps 02:11–02:14 on 2026-04-26 — OpenClaw agent emitting spurious `gog auth add` recommendation despite valid cached Gmail token.
- Existing JARVIS OpenClaw WS integration: `src/integrations/openclaw/`
- Affected JARVIS files targeted for removal: `src/integrations/google/`, `src/actions/web_search.py`
