# OpenClaw Gateway WebSocket Protocol

Reverse-engineered from source (`~/.nvm/versions/node/v24.15.0/lib/node_modules/openclaw/dist/`)
and live-verified with `scripts/openclaw_ws_probe.py`.

---

## Connection

**URL:** `ws://127.0.0.1:18789`

No path suffix needed. The gateway responds on the root WebSocket endpoint.

---

## Handshake (connect.challenge → connect)

### 1. Server sends a challenge immediately on open

```json
{
  "event": "connect.challenge",
  "payload": { "nonce": "<uuid4>" }
}
```

The nonce is a one-time CSRF token. It must be echoed back inside the device
signature payload. It expires if you don't respond promptly (~10 seconds default
`OPENCLAW_CONNECT_CHALLENGE_TIMEOUT_MS`).

### 2. Client sends a `connect` request

Frame format (all gateway messages use this envelope):

```json
{
  "type": "req",
  "id": "<uuid4>",
  "method": "connect",
  "params": { ... }
}
```

The `connect` params shape (current protocol version = 3):

```json
{
  "minProtocol": 3,
  "maxProtocol": 3,
  "client": {
    "id": "gateway-client",
    "version": "probe/1.0",
    "mode": "backend",
    "platform": "linux"
  },
  "caps": [],
  "role": "operator",
  "scopes": [
    "operator.admin",
    "operator.read",
    "operator.write",
    "operator.approvals",
    "operator.pairing",
    "operator.talk.secrets"
  ],
  "auth": {
    "token": "<shared-gateway-token-from-openclaw.json>"
  },
  "device": {
    "id": "<deviceId from ~/.openclaw/identity/device.json>",
    "publicKey": "<32-byte Ed25519 public key, base64url, no padding>",
    "signature": "<Ed25519 signature of payload_str, base64url>",
    "signedAt": 1776451642414,
    "nonce": "<nonce from connect.challenge>"
  }
}
```

#### Signature payload string

Build this string and sign with the Ed25519 private key:

```
v3|<deviceId>|<clientId>|<clientMode>|<role>|<scopes.join(",")>|<signedAtMs>|<auth.token or "">|<nonce>|<platform>|<deviceFamily or "">
```

Example:
```
v3|818935c177a989b2...|gateway-client|backend|operator|operator.admin,operator.read,operator.write,operator.approvals,operator.pairing,operator.talk.secrets|1776451642414|519cd2744ad592...|eda46fe4-...|linux|
```

**Critical:** the scopes order in the payload must match the order in the `scopes`
array in the connect frame — the server rebuilds the payload from the frame and
verifies. Do NOT sort the scopes.

The `auth.token` field from the connect params goes into position 7 of the pipe-
delimited string (`connectParams.auth?.token ?? connectParams.auth?.deviceToken ??
connectParams.auth?.bootstrapToken ?? null`, with `null` becoming `""`).

Public key encoding: strip the 12-byte SPKI prefix
(`302a300506032b6570032100`) from the DER SPKI export, then base64url-encode
the remaining 32 bytes.

### 3. Server responds

```json
{
  "type": "res",
  "id": "<same-uuid-as-req>",
  "ok": true,
  "payload": {
    "type": "hello-ok",
    "protocol": 3,
    "server": { ... },
    "features": { ... },
    "snapshot": { ... },
    "auth": { ... },
    "policy": { "tickIntervalMs": 30000 }
  }
}
```

After this, the server begins sending `{"event": "tick"}` heartbeats at the
interval in `policy.tickIntervalMs` (default 30 000 ms). Ignore ticks.

---

## Event frame (server → client notifications)

```json
{
  "event": "<event-name>",
  "seq": 42,
  "payload": { ... }
}
```

The `seq` increments globally per connection. A gap means you missed an event.

---

## Subscribing to session chat events

Before firing an agent turn, subscribe so the server pushes `chat` events to
your connection:

```json
{
  "type": "req",
  "id": "<uuid4>",
  "method": "sessions.messages.subscribe",
  "params": { "key": "agent:main:explicit:jarvis-ws-probe" }
}
```

Response:
```json
{ "type": "res", "id": "...", "ok": true, "payload": { "subscribed": true, "key": "agent:main:explicit:jarvis-ws-probe" } }
```

To unsubscribe: call `sessions.messages.unsubscribe` with the same `key`.

---

## Running an agent turn

### Step 1 — send `agent` RPC

```json
{
  "type": "req",
  "id": "<uuid4>",
  "method": "agent",
  "params": {
    "message": "Hallo, wie geht's dir?",
    "sessionId": "jarvis-ws-probe",
    "idempotencyKey": "<uuid4>"
  }
}
```

`idempotencyKey` is **required** by the schema. Use a fresh UUID per turn.
`sessionId` is the human-readable session label.  The server resolves it to
`sessionKey = "agent:main:explicit:<sessionId>"` automatically.

Optional params of interest:
- `agentId` — override the default agent (default is `"main"`)
- `thinking` — `"off"` | `"minimal"` | `"low"` | `"medium"` | `"high"` | `"xhigh"`
- `extraSystemPrompt` — injected at runtime into the system prompt

### Step 2 — response frame (immediate, ~3 ms)

```json
{
  "type": "res",
  "id": "<same-uuid-as-req>",
  "ok": true,
  "payload": {
    "status": "accepted",
    "runId": "<idempotencyKey-echoed-back>"
  }
}
```

The `runId` equals the `idempotencyKey` you sent. Use it to match subsequent
`chat` events.

---

## Streaming events (`event: "chat"`)

After the turn is accepted, `chat` events arrive on the WS connection for any
subscribed session. They are **not** sent to a specific request ID — they are
pushed as notifications.

### Delta event (incremental text)

```json
{
  "event": "chat",
  "seq": 3,
  "payload": {
    "runId": "<idempotencyKey>",
    "sessionKey": "agent:main:explicit:jarvis-ws-probe",
    "seq": 1,
    "state": "delta",
    "message": {
      "role": "assistant",
      "content": [{ "type": "text", "text": "1. Apple — crisp and juicy..." }],
      "timestamp": 1776451714000
    }
  }
}
```

The `message.content[0].text` is the **cumulative text so far** (not a raw
token delta). Each delta event contains more text than the previous one.
The server throttles deltas to at most one every 150 ms.

### Final event

```json
{
  "event": "chat",
  "seq": 11,
  "payload": {
    "runId": "<idempotencyKey>",
    "sessionKey": "agent:main:explicit:jarvis-ws-probe",
    "seq": 11,
    "state": "final",
    "message": {
      "role": "assistant",
      "content": [{ "type": "text", "text": "<complete response text>" }],
      "timestamp": 1776451721000
    }
  }
}
```

No `stopReason` field is present in the final chat event (it remains on the
`agent.wait` result). `state: "final"` is the reliable completion signal.

### Error event

```json
{
  "event": "chat",
  "payload": {
    "runId": "...",
    "sessionKey": "...",
    "seq": 5,
    "state": "error",
    "errorMessage": "...",
    "errorKind": "..."
  }
}
```

---

## Cancelling a running turn

```json
{
  "type": "req",
  "id": "<uuid4>",
  "method": "chat.abort",
  "params": {
    "sessionKey": "agent:main:explicit:jarvis-ws-probe",
    "runId": "<runId-to-abort>"
  }
}
```

Source-verified in `acp-cli-Brxbo6fO.js`.

---

## Polling for completion (alternative to streaming)

If you don't want to use streaming events, you can poll:

```json
{
  "type": "req",
  "id": "<uuid4>",
  "method": "agent.wait",
  "params": {
    "runId": "<runId>",
    "timeoutMs": 60000
  }
}
```

Response:
```json
{ "payload": { "status": "ok" | "timeout" | "pending" | "error", "startedAt": ..., "endedAt": ... } }
```

After `status: "ok"`, call `chat.history` to retrieve the final message.

---

## Other useful methods

| Method | Purpose |
|--------|---------|
| `health` | Liveness check (no params needed) |
| `status` | Full gateway status + agent/session summary |
| `sessions.list` | List all sessions |
| `sessions.subscribe` | Subscribe to session lifecycle events (`sessions.changed`) |
| `sessions.abort` | Abort all runs in a session |
| `chat.history` | Get recent messages for a session key |

---

## Gotchas

1. **Delta throttle (150 ms):** The server only emits a delta at most every 150 ms
   per run. For fast responses, the first and last delta may be the only ones you
   receive before `final`.

2. **Cumulative text:** `message.content[0].text` in delta events is always the
   full accumulated text so far — NOT the incremental token. To extract the new
   piece: `text[len(prev_text):]`.

3. **Session key vs session ID:** `sessionId` in `agent` params is the short
   label (e.g. `"jarvis-main"`); `sessionKey` in events is the full canonical
   form (`"agent:main:explicit:jarvis-main"`). Subscribe using the canonical key.

4. **No ping/pong required:** The server sends `{"event":"tick"}` heartbeats
   every ~30 s. No client-side ping needed; the WS library handles TCP keepalive.

5. **Signature staleness:** `signedAt` in the device block must be within ~30 s
   of the current server time (verified: `AUTH_SIGNATURE_EXPIRY_MS = 30_000` in
   source). Generate the signature immediately before sending `connect`.

6. **One connection, many turns:** A single persistent WS connection can handle
   unlimited sequential (and concurrent) agent turns. The `idempotencyKey` + `runId`
   disambiguate concurrent runs.

7. **Auth token in signature:** If the gateway uses `auth.mode = "token"`, the
   shared token must appear both in `auth.token` and in position 7 of the
   signature payload string. Mismatch causes `device-signature` rejection.

8. **Protocol version 3 only:** Gateway rejects connections with
   `maxProtocol < 3` or `minProtocol > 3`. Always send `minProtocol: 3,
   maxProtocol: 3`.

---

## Timing observed (live probe, 2026-04-17)

| Event | Time after `agent` send |
|-------|------------------------|
| `res` (accepted) | ~3 ms |
| First `chat` delta | ~4–5 s (Claude API cold start) |
| Subsequent deltas | every 150–500 ms |
| `final` event | ~8–13 s for a 1 200-char response |

The ~4–5 s delay before the first delta is LLM TTFT (time to first token), not
WS overhead. A persistent WS connection eliminates the 3.7 s subprocess startup
cost entirely.

---

## Tool-call events

**Investigated:** 2026-04-17, via `scripts/openclaw_tool_event_probe.py` (live
gateway at `ws://127.0.0.1:18789`) and source analysis of
`~/.nvm/versions/node/v24.15.0/lib/node_modules/openclaw/dist/`.

### TL;DR — tool events are NOT available to operator WS connections

The gateway has three mechanisms for tool-call events, none of which are
accessible to a backend operator WS connection like JARVIS:

---

### Mechanism 1 — `agent` event stream (`stream: "tool"`)

When a tool call executes, the gateway emits `agent` events with `stream: "tool"`
to connections in the **`toolEventRecipients`** registry.  A connection enters
this registry only if it:

1. Declared the `"tool-events"` capability in the `caps` array of the `connect`
   frame: `"caps": ["tool-events"]`
2. Made the triggering `agent` RPC call from that same connection (the
   registration happens inside the `agent` RPC handler).

Even after adding `"caps": ["tool-events"]` to our connect frame and making the
agent RPC from the same connection, **zero** `agent stream=tool` events were
observed in three live probe runs (different session IDs each time).

Root cause (from source): the `agent` events with `stream="tool"` are only
generated when `shouldSendToolSummaries` is `true` inside the ACP reply
projector.  For raw `agent` WS RPC calls (i.e. calls made directly over the
operator WS, not routed through a Telegram/voice/ACP channel), this flag is
`false` by default.  The control-plane TUI sets it to `true` internally.

Typical `agent stream=tool` payload shape (from source, never observed live):

```json
{
  "event": "agent",
  "seq": 7,
  "payload": {
    "runId": "<uuid>",
    "stream": "tool",
    "sessionKey": "agent:main:explicit:<session-id>",
    "data": {
      "phase": "start" | "end",
      "name": "<tool-name>",
      "title": "<human-readable title>",
      "status": "in_progress" | "completed" | "failed"
    }
  }
}
```

---

### Mechanism 2 — `session.tool` event

When a tool event occurs AND a session key is present, the gateway broadcasts a
`session.tool` event to connections registered via `sessions.subscribe`.  This
event is structurally identical to the `agent stream=tool` payload above, plus
`buildSessionEventSnapshot` fields.

```json
{
  "event": "session.tool",
  "seq": 8,
  "payload": {
    "runId": "<uuid>",
    "stream": "tool",
    "sessionKey": "agent:main:explicit:<session-id>",
    "data": { ... same as agent stream=tool ... }
  }
}
```

**Also not received in live probes.**  Reason: `session.tool` events are only
emitted when `shouldSendToolSummaries` is `true` (same gate as Mechanism 1).

---

### Mechanism 3 — Tool_use content blocks in `chat` message

The `chat` delta and final events contain `message.content` arrays.  Based on
source analysis, only `{type: "text", text: "..."}` blocks appear in the chat
stream.  Tool-use (`{type: "tool_use", ...}`) blocks are NOT embedded in the
chat content — they are processed internally by the Claude Code runner before
the assistant message is published.

Live verified: three runs with confirmed tool execution (bash output in response)
showed only `{type: "text"}` blocks in all chat events, including the final.

---

### JARVIS implementation decision: synthetic tool hints

Since real-time tool events are unavailable, the JARVIS backend uses a **timing
heuristic** to signal tool activity to the frontend:

- If the time between turn start and first text delta (TTFT) exceeds **2 seconds**,
  a synthetic `tool_call` frame is broadcast to the frontend immediately when
  the first token arrives.
- This correlates reliably with actual tool execution: conversational turns
  without tools typically have TTFT < 1 s; tool-calling turns take 4–15 s.

The frame contract is described in `src/api/ws_server.py::broadcast_tool_call`.

---

### JARVIS `tool_call` frame (browser WS, JARVIS → Frontend)

```json
{
  "type": "tool_call",
  "payload": {
    "state": "started" | "finished",
    "tool_name": "Read" | "Bash" | "Write" | "Edit" | "Glob" | "Grep" | "",
    "summary": "Lese config.yaml" | "Führe Shell-Kommando aus" | ""
  }
}
```

Fields:
- `state`: `"started"` when tool work begins, `"finished"` when first text token
  arrives (or tool work ends).
- `tool_name`: empty string for synthetic hints (tool identity unknown).
- `summary`: short German-language label; see `_summarize_tool_call` in
  `src/api/ws_server.py` for the full mapping table.

The frontend should:
1. On `state="started"`: transition orb to `working` state.
2. On `state="finished"`: transition orb back to `thinking` (waiting for more
   text) or `speaking` (if audio already started).
3. Never rely on `tool_name` being non-empty — synthetic hints have `""`.

---

### Future: real-time tool events via ACP channel routing

If OpenClaw ever exposes a way to opt-in to tool event delivery for operator
connections (e.g. a new `agent.verbose` RPC param or a config toggle in
`~/.openclaw/openclaw.json`), the JARVIS ws_client should be updated to:

1. Declare `"caps": ["tool-events"]` in the connect frame.
2. Subscribe via `sessions.subscribe` (already done).
3. Parse `session.tool` events in `_dispatch`, create real `StreamChunk` with
   `type="tool_started"` / `type="tool_finished"`, `tool_name` from
   `payload.data.name`, and route them through the existing pipeline.
