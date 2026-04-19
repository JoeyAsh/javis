# Feature: WhatsApp Butler Agent — Direct Anthropic Runtime for DM Auto-Reply + Ezgi Inbound TTS Notification

## Status
Planned — awaiting implementation authorization

## Goal
WhatsApp DM auto-reply is unreliable because the current `claude-cli/claude-opus-4-7` runtime appends
Claude Code's built-in "coding assistant" system prompt on top of the workspace SOUL.md, causing the two
personas to fight — resulting in `NO_REPLY` on explicit Jarvis mentions (e.g. "hey jarvis. bist du da?")
or spurious replies on follow-up messages that contain no mention. The fix is to introduce a second
OpenClaw agent (`whatsapp-butler`) that uses the `anthropic/` direct API runtime, which loads workspace
bootstrap files without any Claude Code default system prompt overlay, then bind all WhatsApp DM traffic
to this agent while leaving the voice / Control-UI `main` agent on the Claude Max subscription unchanged.
Additionally, when Ezgi sends a WhatsApp message that does not trigger a Jarvis reply (i.e. `NO_REPLY`),
the JARVIS backend must play a TTS announcement on the JARVIS UI so Johannes is verbally informed that
his wife wrote him — but only for her number, and only when Jarvis did not auto-reply to her. The
announcement text is generated per-notification by an LLM call using the JARVIS butler persona (SOUL.md),
not a static template.

## Scope

### In scope
- Add one new entry to `agents.list[]` in `~/.openclaw/openclaw.json` — id `whatsapp-butler`,
  model `anthropic/claude-opus-4-7` (confirmed in OpenClaw 2026.4.15 registry), workspace
  identical to the main agent (`/home/paps/.openclaw/workspace`).
- Add one `bindings[]` route entry in `openclaw.json` routing the `whatsapp` channel to `whatsapp-butler`.
- Patch `openclaw-gateway.service` with `EnvironmentFile=/home/paps/Repos/Jarvis/.env` (preserving
  existing `Environment=` lines) so `ANTHROPIC_API_KEY` is available to the service at runtime.
- Reset the stale `agent:main:main` session record so the new agent starts from a clean session.
- Gateway restart and smoke test.
- Bridge component (OpenClaw managed hook `ezgi-notifier`) that listens on `message:received` and
  `message:sent` events. Implements a 10-second debounce/coalesce window per sender: messages from
  Ezgi are accumulated into a per-sender bucket; a single coalesced `POST /notify/wife` fires after
  the 10-second timer. A `message:sent` event for any message in the window cancels the entire bucket
  (full-window cancellation, not per-message).
- New HTTP endpoint `POST /notify/wife` in the JARVIS aiohttp server on :8766, authenticated by
  sender-id allowlist. On receipt, calls the Anthropic API directly (not via OpenClaw routing) to
  generate a JARVIS-persona announcement sentence, then passes the result to Fish Audio TTS and
  broadcasts synthesized MP3 to connected WebSocket clients via `broadcast_audio(..., channel="notification")`.
- New `notifications.wife.*` config section in `config/config.yaml` (enabled flag, sender_id,
  announcement_model, max_body_chars, fallback_text).
- Frontend audio-queue extension: `useWebSocket`'s audioQueue items gain a `channel` field; the
  consumer in `App.tsx` defers enqueueing `"notification"` clips to `useAudioAnalyser` until all
  in-flight `"speech"` clips have finished playing. `"notification"` clips queue FIFO behind speech.

### Out of scope
- Any edits to workspace files (SOUL.md, AGENTS.md, IDENTITY.md, USER.md, CAPABILITIES.md, TOOLS.md) —
  the existing SOUL.md DM Auto-Reply Policy table is correct; the problem is the runtime, not the prompt.
- Creating new workspace files or new MCP plugins.
- Any change to the `main` agent — voice, Control-UI, and cron turns continue on `claude-cli`.
- Any change to OpenClaw core source code.
- Migrating the `main` agent to the `anthropic/` runtime.
- Restricting the tool set available to `whatsapp-butler` (it inherits all tools from `agents.defaults`,
  same as `main`; scope reduction is a future option flagged in Open Questions).
- TTS announcements for any WhatsApp sender other than +41765005527.
- TTS announcements when the butler auto-replied to Ezgi (i.e. when a `message:sent` event fires for
  the same conversation within the reply window).
- Any visual / frontend UI changes beyond the audio queue channel-awareness — pure audio.
- Streaming the announcement LLM call — single non-streamed completion is sufficient for a short sentence.

## User Flow

### Butler agent (existing fix — unchanged)
1. Ezgi sends "hey jarvis. bist du da?" to Johannes's WhatsApp number.
2. The WhatsApp gateway receives the inbound DM and evaluates `bindings[]`.
3. The `whatsapp` channel binding matches → the turn is dispatched to the `whatsapp-butler` agent.
4. OpenClaw's embedded `anthropic/` runtime spins up (or resumes) session `agent:whatsapp-butler:main`.
5. The runtime bootstraps the system prompt exclusively from workspace files (SOUL.md etc.) with **no**
   Claude Code coding-assistant overlay.
6. The model evaluates the message against SOUL.md's DM Auto-Reply Policy table: sender is Ezgi
   (+41765005527), message contains "jarvis" → emit a warm, Sie-form 1–2 sentence reply.
7. The reply is delivered to Ezgi via the WhatsApp gateway within ~10 seconds.
8. Ezgi's follow-up "danke dir" (no "jarvis" mention) → model emits `NO_REPLY` → silence.

### Ezgi inbound TTS notification (new)
1. Ezgi sends "ich komme um 19 Uhr" (no "jarvis" mention) to Johannes's WhatsApp number.
2. The gateway fires the `message:received` internal hook event (`type: "message"`, `action: "received"`),
   with context including `senderE164: "+41765005527"`, `channelId: "whatsapp"`, and `content`.
3. The `ezgi-notifier` managed hook receives the event. It appends the message body and metadata to the
   per-sender pending bucket and (re)starts a 10-second timer.
4. The butler agent evaluates the message and emits `NO_REPLY`. No `message:sent` event fires for this
   conversation within the timeout window.
5. After the 10-second timeout, the hook POSTs to `http://127.0.0.1:8766/notify/wife` with the full
   batch of accumulated messages.
6. The JARVIS HTTP server validates the payload, calls the Anthropic API to generate a persona-consistent
   announcement sentence, synthesizes TTS via Fish Audio, and broadcasts the resulting MP3 to all
   connected WebSocket clients as a `"notification"` channel audio frame.
7. The frontend receives the audio frame, sees `channel: "notification"`, and holds it until any in-flight
   speech audio finishes. Then it plays the announcement.
8. Johannes hears on his speakers: "Sir, Ihre Frau schreibt, dass sie um 19 Uhr kommt."
9. JARVIS backend logs the event at INFO level with the utterance ID.

### Debounce: Ezgi sends three messages rapidly
1. Ezgi sends "hallo", then "wie geht's", then "bist du da" — all within 5 seconds, none contain "jarvis".
2. Each `message:received` event appends to the same sender bucket and restarts the 10-second timer.
3. After 10 seconds of silence, the hook fires ONE POST with all three bodies in `messages[]`.
4. The JARVIS handler calls the Anthropic API with all three bodies joined, requesting one summary sentence.
5. Johannes hears one announcement summarising all three messages.

### Debounce: cancel via mention
1. Ezgi sends "hallo" and "hey jarvis antworte" — both within 8 seconds.
2. Both messages enter the bucket; timer is (re)started.
3. The butler replies to the mention message; `message:sent` fires.
4. The hook clears the entire bucket and cancels the timer.
5. No POST is sent; Johannes hears nothing. Jarvis already handled the conversation.

Johannes's next voice command routes through the unchanged `main` agent as before — no visible
difference from his perspective.

## Architecture

### Modules touched
- Backend:
  - `src/api/ws_server.py` — add `POST /notify/wife` HTTP route and handler function; add
    `channel="notification"` call-site for `broadcast_audio()`
  - `config/config.yaml` — add `notifications.wife.*` section
- Frontend:
  - `frontend/src/hooks/useWebSocket.ts` — extend `audioQueue` item type to include
    `channel: "speech" | "notification" | "backchannel"`; modify the `audio` case to tag incoming
    frames with channel; expose notification-hold state
  - `frontend/src/hooks/useAudioAnalyser.ts` — extend `enqueue()` signature to accept `channel`
    parameter; implement hold-until-speech logic so `"notification"` items are deferred until all
    `"speech"` items drain
  - `frontend/src/App.tsx` — pass `channel` from the audio queue item through to `enqueue()`
  - `frontend/src/types.ts` — extend `WsIncoming` audio variant's `channel` union to include
    `"notification"`
- Config: `~/.openclaw/openclaw.json` — `agents.list[]`, `bindings[]`, and hook enablement.
- Config: `config/config.yaml` — `notifications.wife.*` keys.
- New hook file: `~/.openclaw/hooks/ezgi-notifier/HOOK.md` and `handler.js` (managed hook, outside
  the JARVIS repo).
- Env: `ANTHROPIC_API_KEY` is already in `/home/paps/Repos/Jarvis/.env`. The
  `openclaw-gateway.service` unit must be patched with
  `EnvironmentFile=/home/paps/Repos/Jarvis/.env` to expose it to the service process.

### Data flow

**Current (broken) flow:**

```
WhatsApp inbound DM
  → gateway receives message
  → no bindings → default agent: main
  → claude-cli runtime spawns claude CLI subprocess
  → Claude Code appends built-in coding-assistant system prompt
    OVER SOUL.md via --append-system-prompt
  → two conflicting personas → safety bias wins
  → NO_REPLY even on "hey jarvis. bist du da?"
```

**Target flow after this change (butler agent — Ezgi mentions "jarvis"):**

```
WhatsApp inbound DM
  → gateway fires message:received (hook sees: senderE164=+41765005527, whatsapp)
  → ezgi-notifier hook: appends to sender bucket; (re)starts 10 s timer
  → bindings[] eval: channel=whatsapp → agentId=whatsapp-butler
  → anthropic/ embedded runtime (pi-embedded-runner path)
      workspace bootstrap: reads /home/paps/.openclaw/workspace/*.md
        identical files as main agent (shared workspace)
      NO Claude Code default system prompt — clean slate
  → MCP tool layer: same plugins.entries.anthropic, gog skill, web tools
  → Anthropic API call (ANTHROPIC_API_KEY from .env via EnvironmentFile=)
  → model decision: SOUL.md policy table → reply text (mention detected)
  → gateway fires message:sent (hook sees: same session/conversation)
  → ezgi-notifier hook: clears ENTIRE sender bucket; cancels timer — NO TTS
  → gateway delivers reply via WhatsApp
```

**Target flow — Ezgi does NOT mention "jarvis" (single or coalesced batch):**

```
WhatsApp inbound DM(s) within 10 s window
  → gateway fires message:received (one or more)
  → ezgi-notifier hook: appends body+timestamp+messageId to sender bucket;
    (re)starts 10 s timer on each arrival
  → bindings[] eval: channel=whatsapp → agentId=whatsapp-butler
  → anthropic/ embedded runtime → NO_REPLY (no mention)
  → no message:sent fires within 10 s
  → 10 s timer fires:
      → POST http://127.0.0.1:8766/notify/wife
          { sender_id: "+41765005527", sender_label: "Ezgi",
            messages: [
              { body: "...", timestamp: "...", message_id: "..." },
              ...
            ] }
  → JARVIS /notify/wife handler:
      truncate each body to max_body_chars (200)
      build user prompt: join bodies into a single user prompt
      call Anthropic API (announcement_model: claude-sonnet-4-6):
        system: trimmed SOUL.md persona extract (~500–800 tokens)
        user: "Ihre Frau Ezgi ... «body1 / body2 / ...»  Formulieren Sie eine
               kurze Ansage (ein Satz, TTS-tauglich, keine Markdown-Formatierung)"
      on API success: utterance = LLM response (≤ ~40 words)
      on API failure: utterance = fallback_text (log WARN)
      call _fish_tts.synthesize(utterance)
      broadcast_audio(audio_b64, utterance_text, channel="notification")
                                              ↓
  → WS frame: { type: "audio", data: "...", text: "...", channel: "notification" }
                                              ↓
  → frontend useWebSocket: audioQueue item { data, volume: 1.0, channel: "notification" }
                                              ↓
  → App.tsx drains queue:
      if channel == "notification" AND speech clips in useAudioAnalyser queue:
        hold — push to notificationHoldQueue
      else:
        enqueue(data, volume, channel) → useAudioAnalyser
                                              ↓
  → useAudioAnalyser: plays after all "speech" clips drain
  → Johannes hears the announcement on his speakers
```

**Voice / Control-UI / cron turns (unchanged):**

```
  → any non-whatsapp channel or explicit session
  → default agent: main (first in agents.list, or agents.defaults)
  → claude-cli runtime (Claude Max OAuth subscription, unchanged)
```

The `anthropic/` runtime reads workspace bootstrap files through the same file-injection mechanism
as `claude-cli` — same paths, same `bootstrapMaxChars` / `bootstrapTotalMaxChars` limits, same
truncation logic. Persona, user knowledge, and capabilities transfer 1:1. The only difference is
that no secondary system prompt is appended by the model provider's CLI shim.

### Hook mechanism (Option α — confirmed viable)

Investigation of the OpenClaw source at `/home/paps/Repos/openclaw/src/` confirms the following:

- **Event: `message:received`** (`type: "message"`, `action: "received"`) — fires on every inbound
  message, before the agent turn. Context type `MessageReceivedHookContext` contains `from`, `content`,
  `channelId`, `accountId`, `conversationId`, `messageId`, and a `metadata` bag that includes
  `senderE164` (the E.164 phone number) and `provider`. Defined in
  `src/hooks/internal-hooks.ts:54–77`.
- **Event: `message:sent`** (`type: "message"`, `action: "sent"`) — fires when an actual reply is
  delivered to the channel. Contains `to`, `content`, `success`, `channelId`, `conversationId`,
  `messageId`. Defined in `src/hooks/internal-hooks.ts:79–106`.
- **Custom hooks without source rebuild** — confirmed possible. The hook loader in
  `src/hooks/loader.ts` scans three directories in order: `~/.openclaw/hooks/` (managed, highest
  practical priority), `<workspace>/hooks/` (workspace), and the bundled directory. Placing the hook
  in `~/.openclaw/hooks/ezgi-notifier/` requires no npm package rebuild, no git change to the
  OpenClaw repo, and no OpenClaw CLI install command.
- **HTTP calls in hooks** — no restrictions in the handler runtime. The hook handler module is a
  plain Node.js ESM module loaded via dynamic `import()`. Node's global `fetch` (available since
  Node 18) or `node:https` are usable directly. The `session-memory` bundled hook uses `node:fs`
  — confirming Node built-ins are available without any special permissions.
- **Hook configuration key** — hooks are enabled/disabled via
  `hooks.internal.entries.<hook-name>.enabled` in `openclaw.json`. A managed hook in
  `~/.openclaw/hooks/ezgi-notifier/` is auto-discovered and enabled by default (no config entry
  needed unless `hooks.internal.enabled` is `false`).

**Why Option α over the alternatives:**
- Option β (agent calls MCP tool) is unreliable by design — the LLM can forget or choose not to call.
- Option γ (log-tail daemon) would work but is brittle across OpenClaw log format changes.
- Option δ (polling) is the worst in all dimensions.
- Option α uses a real event emitted synchronously by the gateway runtime, observable without touching
  OpenClaw source. The `message:received` / `message:sent` pair gives us the exact signal we need.

### Interfaces / Config changes

**JSON diff for `~/.openclaw/openclaw.json` — agents and bindings:**

Add `agents.list` array (does not currently exist — only `agents.defaults` is present):

```json
"agents": {
  "defaults": {
    "memorySearch": { "enabled": false },
    "model": "claude-cli/claude-opus-4-7",
    "workspace": "/home/paps/.openclaw/workspace"
  },
  "list": [
    {
      "id": "main"
    },
    {
      "id": "whatsapp-butler",
      "model": "anthropic/claude-opus-4-7",
      "workspace": "/home/paps/.openclaw/workspace"
    }
  ]
}
```

Notes on `agents.list`:
- The `main` entry is inserted first so `resolveDefaultAgentId` continues to return `"main"` (the
  first entry in the list is the default when none is flagged `"default": true`).
- `whatsapp-butler` uses `anthropic/claude-opus-4-7` — confirmed present in OpenClaw 2026.4.15 registry.
- `whatsapp-butler` explicitly sets the same `workspace` path to force shared workspace rather than
  accepting the fallback logic that would append the agent id to the default path
  (see `resolveAgentWorkspaceDir` in `agent-scope-D-rnqBRA.js`).

Add `bindings` array:

```json
"bindings": [
  {
    "type": "route",
    "agentId": "whatsapp-butler",
    "match": { "channel": "whatsapp" }
  }
]
```

**Environment: patch systemd unit**

Replace the prior recommendation (creating `/home/paps/.openclaw/secret-env`) with the simpler
approach: add `EnvironmentFile=/home/paps/Repos/Jarvis/.env` directly to the `[Service]` section
of `/home/paps/.config/systemd/user/openclaw-gateway.service`, preserving all existing
`Environment=` lines. The key `ANTHROPIC_API_KEY` is already present in the `.env` file; no new
file needs to be created. After editing the unit, run `systemctl --user daemon-reload`.

Note: `openclaw doctor --fix --force` regenerates the unit from scratch and will drop the
`EnvironmentFile=` line. Re-verify and re-add after any future doctor run.

**OpenClaw managed hook files**

```
~/.openclaw/hooks/
└── ezgi-notifier/
    ├── HOOK.md      ← metadata with events: ["message:received", "message:sent"]
    └── handler.js   ← ESM module; default export is the HookHandler function
```

`HOOK.md` frontmatter (YAML block):

```yaml
name: ezgi-notifier
description: "Announces Ezgi WhatsApp DMs via JARVIS TTS when butler emits NO_REPLY"
metadata:
  openclaw:
    emoji: "💬"
    events: ["message:received", "message:sent"]
```

`handler.js` interface (signatures only — no implementation):

```js
// Module-level state:
//   pendingBucket: { bodies: string[], timestamps: string[], messageIds: string[] }
//   bucketTimer: ReturnType<typeof setTimeout> | null
//
// On message:received from senderE164="+41765005527", channelId="whatsapp":
//   append { body, timestamp, messageId } to pendingBucket
//   clearTimeout(bucketTimer); bucketTimer = setTimeout(fireBatch, 10_000)
//
// On message:sent for any conversationId where pendingBucket is non-empty
//   (i.e. any reply was dispatched in the Ezgi whatsapp channel):
//   clearTimeout(bucketTimer); pendingBucket = empty; — full bucket clear
//
// fireBatch():
//   POST "http://127.0.0.1:8766/notify/wife"
//   with { sender_id, sender_label, messages: pendingBucket[] }
//   catch all fetch errors → log to gateway logger, drop silently
//   always: pendingBucket = empty
//
export default async function ezgiNotifierHandler(event) { ... }
```

**Announcement LLM call (inside `notify_wife_handler`)**

The handler does NOT use a static template. Instead it calls the Anthropic API directly:

- Client: `anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])` — uses the key
  already loaded by the JARVIS process (verified: `src/api/ws_server.py` reads the `.env` file
  via `python-dotenv` at startup).
- Model: `notifications.wife.announcement_model` (default `"claude-sonnet-4-6"` for cost/latency;
  opus is not needed for one-sentence generation).
- System prompt: a trimmed SOUL.md extract covering Core Directives, Response Style, Language
  Handling, and Voice Context sections only (approximately 500–800 tokens). The DM Auto-Reply
  Policy section is excluded — it is irrelevant to announcement generation.
- User prompt for text messages:
  `"Ihre Frau Ezgi hat Johannes während einer Abwesenheit eine WhatsApp-Nachricht geschickt: «{joined_bodies}». Formulieren Sie eine kurze Ansage (ein Satz, TTS-tauglich, keine Markdown-Formatierung) für Johannes, um ihn zu informieren."`
- User prompt for media-only batches (all bodies empty):
  `"Ihre Frau Ezgi hat Johannes während einer Abwesenheit ein Foto/Video/eine Sprachnachricht via WhatsApp geschickt. Formulieren Sie eine kurze Ansage (ein Satz, TTS-tauglich, keine Markdown-Formatierung) für Johannes."`
- User prompt for mixed batches: describe both text and media items.
- `joined_bodies`: bodies joined with `" / "`, each truncated to `max_body_chars` (200) characters;
  total joined string truncated to 600 characters to keep prompt bounded.
- `max_tokens`: 80 (sufficient for ≤ 40 words).
- On API success: use `response.content[0].text.strip()` as the utterance.
- On any exception (API error, auth failure, timeout): use `notifications.wife.fallback_text`
  (default: `"Sir, Ihre Frau hat Ihnen eine Nachricht geschickt."`) and log at WARN level.

**New JARVIS REST endpoint**

`POST http://127.0.0.1:8766/notify/wife`

Request JSON (updated to batch format):

```json
{
  "sender_id":    string,    // E.164 phone number, e.g. "+41765005527"
  "sender_label": string,    // display name, e.g. "Ezgi"
  "messages": [
    {
      "body":       string,  // original message text (empty string for media-only)
      "timestamp":  string,  // ISO 8601
      "message_id": string   // provider message ID (for idempotency logging)
    }
  ]
}
```

Success response (HTTP 200):

```json
{
  "accepted": true,
  "utterance_id": string   // UUID generated by the handler for log correlation
}
```

Error response (HTTP 400 / 422):

```json
{
  "accepted": false,
  "error": string
}
```

Handler function signature (Python, in `src/api/ws_server.py`):

```python
async def notify_wife_handler(request: web.Request) -> web.Response: ...
```

The handler must:
1. Validate that `sender_id` matches the configured `notifications.wife.sender_id` allowlist entry.
2. Truncate each `body` in `messages[]` to `notifications.wife.max_body_chars` (default 200) chars.
3. Build the user prompt: join all non-empty truncated bodies. Detect media-only batch if all empty.
4. Call the Anthropic API (`announcement_model`) with the system prompt and user prompt to generate
   one spoken-announcement sentence.
5. On API failure, use `notifications.wife.fallback_text` and log at WARN.
6. Call `await _fish_tts.synthesize(strip_markdown_for_tts(utterance))`.
7. Call `await broadcast_audio(base64(mp3_bytes), utterance_text, channel="notification")`.
8. Return 200 with `{ "accepted": true, "utterance_id": "<uuid>" }`.
9. On `_fish_tts is None` or `FishTTSError` → return 200 with `accepted: true` but log a warning;
   do not return an error to the hook (the message is already delivered on WhatsApp).

**New `config/config.yaml` section:**

```yaml
notifications:
  wife:
    enabled: true
    sender_id: "+41765005527"
    # Model used to synthesize the announcement text (not the TTS audio).
    # Defaults to sonnet for cost/latency; opus is only needed if persona fidelity matters.
    announcement_model: "claude-sonnet-4-6"
    max_body_chars: 200
    fallback_text: "Sir, Ihre Frau hat Ihnen eine Nachricht geschickt."
```

**Frontend: audio queue channel-awareness**

Existing state in `useWebSocket.ts`:
- `audioQueue: Array<{ data: string; volume: number }>` (line 316)
- The `audio` WS message case (line 432–439) appends items to this queue; `channel === "backchannel"`
  sets `volume = 0.3`, all other channels use `volume = 1.0`.

Required changes:

In `frontend/src/types.ts` — extend the `WsIncoming` audio variant:
```ts
channel?: 'backchannel' | 'notification';
// (previously only 'backchannel' was in the union)
```

In `frontend/src/hooks/useWebSocket.ts`:
- Extend the audioQueue item type:
  `Array<{ data: string; volume: number; channel: 'speech' | 'notification' | 'backchannel' }>`
- In the `audio` message case: derive `channel` from `msg.channel`:
  `"backchannel"` → `{ volume: 0.3, channel: "backchannel" }`;
  `"notification"` → `{ volume: 1.0, channel: "notification" }`;
  absent / other → `{ volume: 1.0, channel: "speech" }`.

In `frontend/src/hooks/useAudioAnalyser.ts`:
- Extend `queueRef` item type to `{ data: string; volume: number; channel: string }`.
- Extend `enqueue(base64Mp3, volume, channel)` signature: add `channel = "speech"` parameter.
- Add a `speechPlayingRef: useRef(false)` — set true when a `"speech"` item starts, false when it
  ends or `stopAll()` is called.
- Modify `playNext()`: before starting a `"notification"` item, check if `speechPlayingRef.current`
  is true or any `"speech"` item exists earlier in `queueRef.current`. If so, return without
  playing; the `"notification"` item remains in the queue and `playNext()` is re-invoked from the
  `onended` callback of the preceding speech clip, at which point no more speech items precede it.
- Note: `speechPlayingRef` tracks the CURRENTLY PLAYING item's channel, so that a notification
  arriving while speech is mid-play can correctly defer.

In `frontend/src/App.tsx`:
- Pass `item.channel` from the audio queue item through to `enqueue(item.data, item.volume, item.channel)`.

**Backend: `broadcast_audio` signature**

The existing signature already accepts `channel: str | None`. No new parameter is needed. The
`/notify/wife` handler calls it as:
```python
await broadcast_audio(audio_b64, utterance_text, channel="notification")
```
All existing call-sites remain unchanged (they omit `channel` or pass `"backchannel"`).

**CLI equivalent for reference (not for direct use):**

```bash
openclaw agents add whatsapp-butler \
  --model anthropic/claude-opus-4-7 \
  --workspace /home/paps/.openclaw/workspace \
  --bind whatsapp \
  --non-interactive
```

**Config validation:**

```bash
openclaw config validate
```

Returns exit code 0 on success; prints schema errors on failure.

### External dependencies
- No new pip or npm packages. The `anthropic` Python SDK is already a dependency
  (used elsewhere in the JARVIS backend — verify import exists before adding it).
- `ANTHROPIC_API_KEY` already exists in `/home/paps/Repos/Jarvis/.env`. The `EnvironmentFile=`
  directive in the systemd unit exposes it to the OpenClaw service process. The JARVIS Python
  backend already loads `.env` at startup via `python-dotenv`.
- No new Home Assistant services or OS-level deps.

## Edge Cases & Failure Modes

### Butler agent (existing)

- **Anthropic API down or rate-limited** → OpenClaw's delivery-queue picks up the undelivered reply
  and retries on the configured retry policy. No automatic failover to `claude-cli` is in place —
  this is intentional, since `claude-cli` is what we are escaping. Messages queue silently; Ezgi
  sees no reply until the API recovers.

- **Both agents running concurrently, writing to shared workspace** → Session tracking is isolated
  by session key (`agent:main:main` vs `agent:whatsapp-butler:main`). The `.jsonl` transcript files
  live in separate directories. If both agents use a memory-write MCP tool simultaneously targeting
  the same file in `/home/paps/.openclaw/workspace/memory/`, a write race exists at the filesystem
  level — no `flock` logic observed in OpenClaw. In practice the risk is low; WhatsApp DMs are
  infrequent. Accept for now; revisit if corruption is observed.

- **`agents.list` default-agent resolution** → The `main` entry must appear first in the list,
  otherwise voice and cron turns silently route to `whatsapp-butler`.

- **Shared workspace but diverging session history** → After the switch, WhatsApp traffic routes to
  `agent:whatsapp-butler:main` with no prior Ezgi DM history. Each DM is evaluated stateless per
  SOUL.md policy, so this is functionally acceptable, but any ongoing conversational topic context
  with Ezgi is lost at the cut-over.

- **`ANTHROPIC_API_KEY` absent from systemd environment** → If the `EnvironmentFile=` line is
  missing and the service restarts, every Anthropic API call fails with an authentication error.
  Messages queue but are never delivered. The `EnvironmentFile=` patch is a mandatory prerequisite
  before gateway restart.

- **MCP tool compatibility between runtimes** → The `gog` calendar skill and
  `plugins.entries.anthropic` MCP plugin are configured globally. It is not verified that these
  tools are accessible under the embedded `anthropic/` runtime the same way they are under
  `claude-cli`. Acceptable for initial rollout; flag in Open Questions.

- **`resolveAgentWorkspaceDir` fallback behavior** → If `workspace` is omitted from the
  `whatsapp-butler` list entry, OpenClaw appends the agent id to the default workspace path:
  `/home/paps/.openclaw/workspace/whatsapp-butler/` (empty — no SOUL.md). The explicit `workspace`
  field in the list entry is therefore required.

- **`openclaw doctor --fix` overwriting the unit** → `openclaw doctor --fix --force` regenerates
  the systemd unit from scratch and drops the `EnvironmentFile=` line. After any future doctor run,
  re-verify and re-add the directive.

### Ezgi inbound TTS notification (new)

- **Hook POST fails (JARVIS backend offline)** → The `fetch()` call in the hook rejects. The hook
  catches the error, logs it to the gateway logger, and drops the notification silently. No retry.
  The message is already delivered to WhatsApp; Johannes will see it on his phone.

- **`_fish_tts` is `None` at notification time** → The handler returns HTTP 200 with
  `accepted: true` but logs a warning. No TTS is produced; the browser hears nothing. This can
  happen if the JARVIS backend is starting up. Acceptable.

- **`FishTTSError` during synthesis** → Caught; log at ERROR level; return 200 with
  `accepted: true`. No retry from the hook. Same acceptability rationale as above.

- **Anthropic API failure during announcement generation** → Handler catches the exception, logs
  at WARN, and uses `notifications.wife.fallback_text` as the utterance. Johannes still hears an
  announcement ("Sir, Ihre Frau hat Ihnen eine Nachricht geschickt."). No body content is spoken in
  this case, which is an acceptable degradation.

- **`ANTHROPIC_API_KEY` not in JARVIS backend environment** → The announcement API call raises an
  `AuthenticationError`. Handled identically to the general Anthropic API failure case above —
  fallback text is used and the failure is logged at WARN. Note: the JARVIS backend reads `.env`
  via `python-dotenv` at startup; this failure mode is only possible if the key was not set.

- **Long message body** → Each body is truncated to `notifications.wife.max_body_chars` (200)
  characters before joining. The combined joined string is truncated to 600 characters before
  building the user prompt. Truncation adds an ellipsis ("…") where the body was shortened.

- **Media-only message (no text body)** → All bodies in the batch are empty. The handler detects
  this and uses the media-specific user prompt variant
  ("ein Foto/Video/Sprachnachricht"). This covers image, video, audio, and document shares.

- **Rapid-fire messages from Ezgi (debounce window)** → Messages arriving within 10 seconds of
  each other are coalesced into a single notification. A continuous flurry of messages all within
  the window rolls into ONE POST. Only after 10 seconds of silence does the batch fire.

- **Two messages arriving 20+ seconds apart** → Each message starts its own 10-second timer. If
  no new message arrives within 10 seconds of the first, it fires independently. The second message
  then starts a fresh bucket. Two separate announcements play.

- **`message:sent` arrival clears entire bucket** → When the butler replies to any Ezgi message in
  the window (typically a mention message), the entire bucket is cleared and the timer cancelled.
  This is intentional: if Jarvis is already handling the conversation, Johannes does not need an
  interruption for the surrounding context messages. The alternative (per-message cancellation)
  is deferred per user decision.

- **Hook timer race: reply arrives just after 10 s timer fires** → If the API is slow and the
  reply arrives milliseconds after the hook already POSTed, Johannes receives both the WhatsApp
  reply and a TTS announcement. Low probability (10 s is a wide window). Accept for now.

- **Multiple pending messages and conversationId matching** → The hook uses a single per-sender
  bucket (not per-messageId). A `message:sent` from the Ezgi whatsapp conversation clears the whole
  bucket regardless of which specific message was replied to.

- **Notification audio arrives while JARVIS is speaking** → The `broadcast_audio(..., channel="notification")`
  WS frame is received by the frontend. The audio queue item is tagged `channel: "notification"`.
  The frontend defers its enqueue to `useAudioAnalyser` until all `"speech"` items in the
  `useAudioAnalyser` internal queue have drained. The notification plays after the speech finishes,
  with no interruption or overlap.

- **Multiple notifications queuing during a long voice turn** → All `"notification"` items remain
  in the `useAudioAnalyser` queue behind speech items. They play back-to-back after speech drains,
  in arrival order (FIFO).

- **Notification arrives when no speech is playing** → `speechPlayingRef.current` is false and no
  `"speech"` items precede it in the queue. The notification plays immediately (same behavior as a
  speech clip in an empty queue).

- **`barge_in` event while notification is queued** → `barge_in` calls `stopAll()` in
  `useAudioAnalyser`, which clears the entire internal queue (including any queued notifications).
  This is acceptable — barge-in signals a new voice turn is starting, which takes priority.

- **Raspberry Pi / Docker targets** → This feature modifies only the local
  `~/.openclaw/openclaw.json`, the local systemd user unit, a managed hook in
  `~/.openclaw/hooks/`, and `config/config.yaml`. The frontend and backend changes are in the JARVIS
  repo and deploy normally. RPi and Docker deployments of JARVIS receive the `config.yaml` and
  source changes via version control; the OpenClaw-side changes are host-local.

- **`/notify/wife` endpoint accessible from other processes** → The HTTP server binds to
  `0.0.0.0` on :8766. Security is enforced at the application layer by validating `sender_id`
  against the configured allowlist. Only `+41765005527` is in the allowlist; any other `sender_id`
  returns HTTP 403. This is sufficient for a home network.

## Acceptance Criteria

1. `openclaw config validate` exits with code 0 and prints no errors after the config edit.
2. `openclaw agents list --bindings --json` shows two agents (`main`, `whatsapp-butler`) and one
   route binding (`whatsapp` → `whatsapp-butler`).
3. `systemctl --user show openclaw-gateway.service --property=EnvironmentFiles` returns a non-empty
   value referencing `/home/paps/Repos/Jarvis/.env`.
4. `systemctl --user is-active openclaw-gateway.service` returns `active` after restart — no crash
   within 30 seconds of start.
5. Sending a WhatsApp message with no "jarvis" mention from Ezgi's number (+41765005527) produces
   zero outbound WhatsApp messages within 15 seconds (observable via gateway log: no reply event).
6. Sending "hey jarvis. bist du da?" from Ezgi's number produces a non-empty Sie-form reply
   delivered to WhatsApp within 10 seconds.
7. Sending a second message "danke dir" (no mention) immediately after criterion 6's reply produces
   `NO_REPLY` — silence on Ezgi's screen.
8. A voice interaction from Johannes (via JARVIS Python backend → WebSocket) still resolves to
   session `agent:main:main` in the gateway logs — not `agent:whatsapp-butler:main`.
9. `ls ~/.openclaw/agents/whatsapp-butler/sessions/` shows a `sessions.json` file populated after
   the first successful WhatsApp turn.
10. `grep modelProvider ~/.openclaw/agents/whatsapp-butler/sessions/sessions.json` returns
    `"modelProvider":"anthropic"` (not `claude-cli`).
11. `ls ~/.openclaw/agents/main/sessions/*.jsonl` count is unchanged from pre-implementation
    (WhatsApp turns no longer append to the main agent's transcript).
12. `openclaw config validate` continues to exit 0 after two gateway restarts.
13. Sending a non-mention DM from Ezgi's number (+41765005527) — and waiting 10 seconds after the
    last message — triggers exactly ONE audible TTS announcement on Johannes's speakers (observable:
    audio plays in the JARVIS UI browser tab; gateway log shows `POST /notify/wife` received once;
    ws_server log shows utterance synthesized once).
14. Sending "hey jarvis. wie spät ist es?" from Ezgi triggers a WhatsApp reply AND does NOT trigger
    a TTS announcement (observable: no `POST /notify/wife` in ws_server log for this message).
15. Sending from any other number (any non-Ezgi number) triggers neither a WhatsApp reply nor a TTS
    announcement.
16. `POST http://127.0.0.1:8766/notify/wife` with a correctly-formatted batch payload returns
    HTTP 200 with `{ "accepted": true, "utterance_id": "<non-empty string>" }` and logs the event
    at INFO level in the ws_server log.
17. `POST /notify/wife` with `sender_id` not in the configured allowlist returns HTTP 403.
18. A body longer than 200 characters is truncated to 200 characters (with trailing ellipsis) in
    the TTS utterance (observable: synthesized text in ws_server log is ≤ 200 chars plus ellipsis,
    per message).
19. A media-only batch (all bodies empty) produces an announcement describing a photo/video/voice
    message rather than a blank or `«»` placeholder (observable: ws_server log shows the utterance
    text contains "Foto", "Video", or equivalent persona-generated wording).
20. The announcement text generated for a plain-text batch from Ezgi contains the body content (or
    a recognizable paraphrase) and is in Sie-form when the body is German (observable: ws_server log
    shows utterance text; manual review of wording).
21. The announcement text varies across three identical test payloads sent several minutes apart —
    non-static LLM output (observable: compare utterance text in ws_server log across three calls;
    at least 2 of 3 must differ in wording).
22. A forced Anthropic API failure in the announcement call (achieved by temporarily setting
    `ANTHROPIC_API_KEY` to an invalid value in the JARVIS process environment) results in the
    fallback text `"Sir, Ihre Frau hat Ihnen eine Nachricht geschickt."` being spoken and a WARN
    log line appearing in ws_server.log.
23. Three non-mention Ezgi messages sent within 5 seconds produce ONE audible TTS announcement (not
    three), and the announcement text summarises or references all three bodies (observable: one
    `POST /notify/wife` in ws_server log, 10 seconds after the last message; utterance text visible).
24. Two non-mention messages sent 20 seconds apart produce TWO separate TTS announcements (observable:
    two `POST /notify/wife` entries in ws_server log, each followed by a distinct utterance).
25. A mention message arriving within the 10-second window of two prior non-mention messages
    CANCELS the entire pending bucket: no `POST /notify/wife` fires for any of the three messages
    (observable: gateway log shows `message:sent` before timer expiry; no `POST /notify/wife`).
26. While JARVIS is playing a long spoken reply (≥ 10 seconds of TTS audio from a voice command),
    a `/notify/wife` notification arriving mid-stream does NOT interrupt or overlap the speech —
    the speech finishes completely, then the notification plays (observable: audio in browser tab;
    no overlap; sequential play).
27. Two notifications arriving within 1 second of each other during a long speech both play after
    the speech ends, in arrival order (first notification's utterance plays first; second follows
    immediately after).

## Implementation Plan

1. `backend-dev` → Back up `~/.openclaw/openclaw.json` to
   `/tmp/openclaw.json.bak.<unix-timestamp>` before any edits.
2. `backend-dev` → Edit `~/.openclaw/openclaw.json`: add `agents.list` array with entries
   `{ "id": "main" }` and `{ "id": "whatsapp-butler", "model": "anthropic/claude-opus-4-7",
   "workspace": "/home/paps/.openclaw/workspace" }`, preserving all existing keys and formatting.
3. `backend-dev` → Edit `~/.openclaw/openclaw.json`: add top-level `bindings` array with one
   `{ "type": "route", "agentId": "whatsapp-butler", "match": { "channel": "whatsapp" } }` entry.
4. `backend-dev` → Run `openclaw config validate` and confirm exit code 0; abort and restore backup
   if it fails.
5. `backend-dev` → Add `EnvironmentFile=/home/paps/Repos/Jarvis/.env` to the `[Service]` section
   of `/home/paps/.config/systemd/user/openclaw-gateway.service` (preserve all existing
   `Environment=` lines), then run `systemctl --user daemon-reload`.
6. `backend-dev` → Rename (do not delete) the stale main-agent session JSONL files that contain
   WhatsApp history, and reset `agent:main:main` in
   `~/.openclaw/agents/main/sessions/sessions.json` so the whatsapp-butler starts fresh.
   Exact approach: rename the old `.jsonl` referenced by `agent:main:main` to
   `<filename>.reset.<timestamp>` and remove the `agent:main:main` key from `sessions.json`.
7. `backend-dev` → Restart the gateway: `systemctl --user restart openclaw-gateway.service`;
   confirm `is-active` returns `active` within 10 seconds.
8. `backend-dev` → Run `openclaw agents list --bindings --json` and confirm two agents and one
   binding appear; run `openclaw config validate` again to confirm the gateway has not overwritten
   the config.
9. `backend-dev` → Add `notifications.wife.*` section to `config/config.yaml` with keys `enabled`,
   `sender_id`, `announcement_model`, `max_body_chars`, `fallback_text` and defaults as documented
   in Interfaces above.
10. `backend-dev` → Add `notify_wife_handler` async function and register route
    `http_app.router.add_post("/notify/wife", notify_wife_handler)` in `src/api/ws_server.py`.
    Handler reads from config, validates `sender_id`, truncates bodies, builds user prompt, calls
    Anthropic API for announcement text, falls back to `fallback_text` on API error, calls
    `_fish_tts.synthesize()`, calls `broadcast_audio(..., channel="notification")`, and returns the
    JSON response. Must use `loguru` logger (no `print()`). Must handle `_fish_tts is None` and
    `FishTTSError` gracefully.
11. `backend-dev` → Create `~/.openclaw/hooks/ezgi-notifier/HOOK.md` with the metadata frontmatter
    declaring events `["message:received", "message:sent"]` as documented in Interfaces above.
12. `backend-dev` → Create `~/.openclaw/hooks/ezgi-notifier/handler.js` as a plain Node.js ESM
    module. Handler logic: maintain a module-level `pendingBucket` (array of message objects) and
    `bucketTimer`. On `message:received` from `senderE164 === "+41765005527"` and
    `channelId === "whatsapp"`: append body+timestamp+messageId to bucket; `clearTimeout(bucketTimer)`;
    `bucketTimer = setTimeout(fireBatch, 10_000)`. On `message:sent` for Ezgi's whatsapp
    conversation (any message — full-bucket cancellation): `clearTimeout(bucketTimer)`;
    `pendingBucket = []`. `fireBatch()`: POST to `http://127.0.0.1:8766/notify/wife` with
    `{ sender_id, sender_label, messages: pendingBucket }`; catch all fetch errors and log;
    always reset `pendingBucket = []`. Never throw from the handler.
13. `backend-dev` → Restart the gateway again (`systemctl --user restart openclaw-gateway.service`)
    so the new hook in `~/.openclaw/hooks/` is picked up by `loadInternalHooks`.
14. `frontend-dev` → Extend `WsIncoming` audio variant in `frontend/src/types.ts`: add
    `"notification"` to the `channel` union (`channel?: 'backchannel' | 'notification'`).
15. `frontend-dev` → Extend the audio queue item type in `frontend/src/hooks/useWebSocket.ts`:
    add `channel: 'speech' | 'notification' | 'backchannel'` field; update the `audio` message
    case to derive and store the channel on each queue item.
16. `frontend-dev` → Extend `useAudioAnalyser.ts`: add `channel` parameter to `enqueue()`; add
    `speechPlayingRef` to track when the active clip is `"speech"`; modify `playNext()` to defer
    `"notification"` items while any `"speech"` clip is playing or precedes them in the queue.
17. `frontend-dev` → Update `frontend/src/App.tsx`: pass `item.channel` to `enqueue()` in the
    `audioQueue` drain effect.
18. `tester` → Unit tests for `notify_wife_handler` in `tests/test_notify_wife.py`:
    - Valid payload returns 200 + `accepted: true`.
    - Invalid `sender_id` returns 403.
    - `_fish_tts is None` returns 200 with warning logged (mock logger).
    - `FishTTSError` returns 200 with error logged.
    - Anthropic API failure uses fallback_text and logs WARN.
    - Body truncation at `max_body_chars` applies ellipsis.
    - Media-only batch (all empty bodies) uses the media-variant user prompt.
    All external calls (Fish TTS, Anthropic SDK) must be mocked.
19. `tester` → Component/hook tests for audio queue channel-awareness in
    `frontend/src/hooks/__tests__/useWebSocket.test.ts`:
    - `audio` WS message with `channel: "notification"` produces a queue item with `channel: "notification"`.
    - `audio` WS message with no channel produces a queue item with `channel: "speech"`.
    - `audio` WS message with `channel: "backchannel"` produces `volume: 0.3` and `channel: "backchannel"`.
20. `tester` → Unit tests for `useAudioAnalyser.ts` notification-hold logic:
    - `enqueue("speech")` followed by `enqueue("notification")` plays speech first, then notification.
    - `enqueue("notification")` with no speech in-flight plays immediately.
    - `stopAll()` clears both speech and notification items from the queue.
21. `reviewer` → Verify all 27 Acceptance Criteria against live system state and test results;
    produce a `PASS` / `NEEDS_CHANGES` verdict.

## Manual Verification

After step 13 completes, run the following live checks:

```bash
# 1. Confirm config is valid
openclaw config validate

# 2. Confirm agents and binding
openclaw agents list --bindings --json | python3 -m json.tool

# 3. Confirm gateway is alive
systemctl --user is-active openclaw-gateway.service

# 4. Confirm EnvironmentFile is present in the unit
grep EnvironmentFile /home/paps/.config/systemd/user/openclaw-gateway.service

# 5. Confirm hook is registered in gateway logs
journalctl --user -u openclaw-gateway.service -n 50 | grep ezgi-notifier

# 6. Smoke-test the /notify/wife endpoint directly (single message in batch)
curl -s -X POST http://127.0.0.1:8766/notify/wife \
  -H "Content-Type: application/json" \
  -d '{
    "sender_id": "+41765005527",
    "sender_label": "Ezgi",
    "messages": [
      { "body": "Test Nachricht", "timestamp": "2026-04-19T18:00:00.000Z", "message_id": "test-001" }
    ]
  }' | python3 -m json.tool
# Expected: {"accepted": true, "utterance_id": "<uuid>"}
# Expected: LLM-generated announcement audible in the JARVIS browser tab (persona-consistent sentence)

# 7. Smoke-test multi-message batch
curl -s -X POST http://127.0.0.1:8766/notify/wife \
  -H "Content-Type: application/json" \
  -d '{
    "sender_id": "+41765005527",
    "sender_label": "Ezgi",
    "messages": [
      { "body": "hallo", "timestamp": "2026-04-19T18:00:00.000Z", "message_id": "t-01" },
      { "body": "wie gehts", "timestamp": "2026-04-19T18:00:02.000Z", "message_id": "t-02" },
      { "body": "bist du zu hause", "timestamp": "2026-04-19T18:00:04.000Z", "message_id": "t-03" }
    ]
  }' | python3 -m json.tool
# Expected: single summary announcement covering all three messages

# 8. Tail gateway log while running live WhatsApp test
journalctl --user -u openclaw-gateway.service -f --since "1 minute ago"
```

Then ask Ezgi (+41765005527) to send these messages in order:

1. "hallo schatz", then "ich komme um 19 Uhr", then "kauf noch Milch" — all within 5 seconds:
   - Silence on Ezgi's screen.
   - After 10 seconds: ONE audible LLM-generated announcement on Johannes's JARVIS speakers,
     summarising all three messages in SOUL.md persona.
   - Gateway log: three `message:received` events; one `POST /notify/wife` fired 10 s after last.
2. Wait 20 seconds, then send "hey jarvis. wie spät ist es?":
   - Sie-form WhatsApp reply from Jarvis within 10 s.
   - NO TTS announcement on Johannes's speakers.
3. Send "danke dir", then immediately "hey jarvis" — both within 8 seconds:
   - The mention message triggers a reply; `message:sent` fires.
   - Entire bucket cleared; timer cancelled.
   - No TTS announcement for either message.
4. While JARVIS is giving a long spoken reply (e.g. to a weather question), trigger a
   `/notify/wife` POST via curl:
   - Speech finishes uninterrupted.
   - Announcement plays immediately after speech ends.

Finally, issue a voice command to JARVIS ("What time is it?") and confirm the gateway log shows
`agent:main:main` — not `agent:whatsapp-butler:main`.

## Open Questions

2. **API cost acceptance.** Order-of-magnitude monthly estimate: 20 Ezgi messages/day, 90% produce
   `NO_REPLY` → 2 real replies/day. Each real reply: ~3 000 input tokens (workspace bootstrap +
   message history) + ~80 output tokens. The 90% `NO_REPLY` messages still incur inference cost:
   18/day × 30 = 540 turns × 3 000 tokens = 1.62 MTok input → ~$24/month. Announcement generation
   adds ~18/day × 30 = 540 calls at ~600 input + 80 output tokens on `claude-sonnet-4-6` (~$0.50
   total/month) — negligible. Total: roughly **~$27/month** at full-message-count inference.
   Confirm willingness to pay the higher bound before implementation.

3. **MCP tool compatibility under `anthropic/` runtime.** The `gog` calendar skill and
   `plugins.entries.anthropic` MCP plugin are confirmed globally configured. It is not empirically
   verified that these tools are accessible to the `whatsapp-butler` agent under the embedded
   `anthropic/` runtime. If calendar tools are unavailable, that is acceptable for initial rollout.
   Confirm whether full tool parity is required at launch.

4. **Tool set scope for `whatsapp-butler`.** User confirmed "the same tools as main". A restricted
   subset would reduce blast radius. Defaulting to full/shared per user confirmation; flagging for
   explicit acknowledgment.

5. **Should the `main` agent eventually migrate to `anthropic/` runtime?** The voice pipeline
   benefits from Claude Max's 5× usage cap, only available via the `claude-cli` OAuth path. Keep
   `main` on `claude-cli` indefinitely unless the subscription model changes. Confirm.

6. **Operator alert on Anthropic API outage.** If the Anthropic API is unavailable, WhatsApp DMs
   queue silently. Is a notification to Johannes wanted, or is silent queue-and-retry acceptable?

10. **`anthropic` Python SDK availability.** The `notify_wife_handler` calls the Anthropic SDK
    directly. Verify `anthropic` is already listed in `requirements.txt` / `pyproject.toml`; if not,
    add it (it is the only new backend dep). No version constraint is required beyond what the
    existing codebase already pins.

11. **SOUL.md persona extract for announcement system prompt.** The spec calls for a trimmed extract
    of SOUL.md's Core Directives, Response Style, Language Handling, and Voice Context sections
    (~500–800 tokens). The exact text and section boundaries depend on the current SOUL.md content.
    The backend-dev agent must read SOUL.md and extract only these sections; do not embed the full
    file (too long) or the DM Auto-Reply Policy table (irrelevant). Confirm the section names match
    the current SOUL.md headings before implementing.

---

## Revision 1 — 2026-04-19

Incorporated the following changes relative to the original planning document:

- **ANTHROPIC_API_KEY resolved**: replaced the `secret-env` file recommendation with the simpler
  `EnvironmentFile=/home/paps/Repos/Jarvis/.env` approach; removed the corresponding Open Question.
- **Ezgi inbound TTS notification**: full new feature scope added — hook mechanism, JARVIS HTTP
  endpoint, config section, data flow diagram, edge cases, and 7 new acceptance criteria.
- **Option α confirmed**: verified from OpenClaw source that `message:received` fires with
  `senderE164` before the agent turn, and `message:sent` fires when a real reply is dispatched.
  Managed hook in `~/.openclaw/hooks/` confirmed viable without source rebuild. Alternatives β/γ/δ
  documented and discarded.

## Revision 2 — 2026-04-19

- **Model ID updated**: `anthropic/claude-opus-4-6` → `anthropic/claude-opus-4-7` everywhere (confirmed
  present in OpenClaw 2026.4.15 registry). Open Question 1 removed as answered.
- **Dynamic TTS announcement via LLM**: replaced static `template` / `media_template` config keys
  and string-formatting logic with a direct Anthropic API call inside `notify_wife_handler`. New
  config keys `announcement_model` (default `claude-sonnet-4-6`) and `fallback_text` replace the
  old `template` / `media_template` keys. System prompt embeds trimmed SOUL.md persona extract.
  Open Questions 7 (template wording) removed as resolved.
- **Debounce / coalesce window**: per-sender bucket with 10-second rolling timer replaces per-messageId
  tracking. `message:sent` clears the entire bucket (not per-message cancellation). POST payload
  changed to batch format with `messages[]` array. Open Question 8 (debounce policy) removed as
  resolved.
- **Audio queue channel-awareness (non-interrupt guarantee)**: frontend `audioQueue` items gain a
  `channel` field; `useAudioAnalyser.ts` defers `"notification"` clips until all `"speech"` clips
  drain; `App.tsx` and `types.ts` updated accordingly. Backend `broadcast_audio` already supported
  `channel` — call-site updated to pass `channel="notification"`. Open Question 9 (interrupt vs queue)
  removed as resolved.
- **Acceptance criteria**: grew from 19 to 27 (added criteria 20–27 covering LLM output validation,
  debounce behavior, and non-interrupt audio guarantee).
- **Implementation Plan**: grew from 14 to 21 steps (added frontend steps 14–17, tester steps 18–20,
  reviewer updated to step 21).
- **Open Questions**: resolved 1, 7, 8, 9. Added new Open Questions 10 (anthropic SDK availability)
  and 11 (SOUL.md section names for persona extract). Retained 2, 3, 4, 5, 6.

---

READY FOR AUTHORIZATION — implementation will not begin until user confirms.
