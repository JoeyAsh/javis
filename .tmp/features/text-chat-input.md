# Feature Spec: Text Chat Input in Transcript Panel

## Summary
Add a text input to the `TranscriptPanel` so the user can converse with JARVIS by typing — not only by voice. Today the panel is read-only (mitlesen). After this feature the user can submit a typed message that runs through the same brain/LLM/TTS pipeline as a spoken turn. This is the keyboard-first counterpart to the existing wake-word + STT path, useful in quiet environments, on phones without a working mic, or while debugging.

## Goals
- Type a message in the expanded `TranscriptPanel` and submit it (Enter) to JARVIS.
- Submitted text appears immediately in the transcript as a `user` turn, identical in look to a voice-derived user turn.
- Backend treats the typed text as if it had just come out of STT — same orchestrator, same TTS, same follow-up window, same conversation memory.
- STOP / cancel-turn still works for an in-flight text turn.
- Input is disabled (greyed) while WS is disconnected, while a turn is in flight, and while audio is playing back, but stays focused so the user can resume typing immediately when ready.
- Multi-line input via Shift+Enter; plain Enter submits.

## Non-Goals
- Slash commands or rich formatting in the input (plain text only — Phase B).
- File / image attachments in chat (Phase B).
- Markdown rendering of JARVIS replies in the transcript (the existing transcript treats text as plain — keep that here).
- Compact-mode input — only the expanded `TranscriptPanel` gets the input row. Compact stays read-only.
- Editing or retracting a sent message.
- Replacing voice input — voice path stays unchanged and is the primary modality.

---

## Architecture

### Frontend
```
frontend/src/
  components/panels/
    TranscriptPanel.tsx       # add <ChatInput/> at the bottom in expanded mode
    ChatInput.tsx             # NEW — controlled textarea + submit logic
  hooks/
    useChatSubmit.ts          # NEW — wraps sendTranscript, exposes {submit, busy, disabled}
```

### Backend
```
src/api/
  ws_server.py                # _handle_command: add cmd_type == "transcript"
                              # NEW _run_text_pipeline(text, ws) — voice pipeline minus STT
```

### Data flow
```
[ChatInput] --Enter--> useChatSubmit.submit(text)
       --> sendTranscript(text)             (existing in useWebSocket)
       --> WS: {type:"transcript", text, isFinal:true}
       --> ws_server._handle_command
       --> _run_text_pipeline(text, ws)
              ├─ broadcast user turn  ({type:"transcript", payload:{role:"user", text}})
              ├─ broadcast_state("thinking")
              ├─ orchestrator.handle(text)
              ├─ TTS → audio frames
              └─ broadcast jarvis turn + arm follow-up window
```

The user-turn broadcast that backends already emit after STT (`{"type":"transcript","payload":{"role":"user","text":...}}`, line 251 of `ws_server.py`) is reused — frontend does **not** locally append the user message. Single source of truth: backend echoes it back, so disconnects/reloads stay consistent with what JARVIS actually heard.

---

## Frontend: `ChatInput.tsx`

### Interface
```tsx
export interface ChatInputProps {
  /** Disabled outside `connected` or while a turn is in flight. */
  disabled?: boolean;
  /** Called with trimmed, non-empty text on submit. */
  onSubmit: (text: string) => void;
  /** Optional placeholder; defaults to "Sprich oder schreib mit JARVIS …". */
  placeholder?: string;
}

export function ChatInput(props: ChatInputProps): ReactElement;
```

### Behaviour
- Auto-growing `<textarea>`, max height ~120 px, then scrolls.
- **Enter** → submit (preventDefault). **Shift+Enter** → newline.
- Trims input; no-op on empty / whitespace-only.
- Clears on successful submit.
- Stays focused after submit so the next message can be typed immediately.
- `disabled` greys the field, blocks submit, but does **not** blur it.
- `aria-label="JARVIS Chat-Eingabe"` on the textarea.
- Visual style matches the design system (`var(--accent)`, `var(--border)`, `var(--text)`) and the dark-on-dark transcript area. No box-shadow; 1 px border; subtle focus ring in `var(--accent)`.

### `useChatSubmit.ts`
Thin wrapper around `useWebSocket().sendTranscript` and orb state:
```ts
export interface UseChatSubmitReturn {
  submit: (text: string) => void;
  /** True while a turn is in flight (orb !== 'idle' & !== 'listening'). */
  busy: boolean;
  /** True when input should be disabled (no WS, busy, or audio playing). */
  disabled: boolean;
}
export function useChatSubmit(): UseChatSubmitReturn;
```
`busy` is derived from the orb state already exposed by `useWebSocket` (`thinking | speaking | working`). `disabled = !connected || busy`.

### `TranscriptPanel.tsx` change
- In `TranscriptExpanded`, after the messages list, render `<ChatInput onSubmit={submit} disabled={disabled} />`.
- `bottomRef` scroll-into-view stays the last element.
- `TranscriptCompact` is unchanged.

---

## Backend: `ws_server.py` changes

### 1. Route `transcript` command
In `_handle_command` (around line 2628), add before the `else` branch:
```python
elif cmd_type == "transcript":
    text = (data.get("text") or "").strip()
    is_final = bool(data.get("isFinal", True))
    if text and is_final:
        await _start_text_pipeline(text, ws)
```

### 2. Replace voice-only pipeline scheduling with a thin `_start_text_pipeline`
```python
async def _start_text_pipeline(text: str, ws: web.WebSocketResponse) -> None:
    """Schedule a brain/TTS turn from typed text — STT-bypass equivalent of
    the silence-detector branch in _process_audio_for_client.
    """
    state = _connection_state.get(id(ws))
    if state is None:
        return
    # If a turn is already running, ignore (frontend should disable input,
    # but be defensive).
    existing = state.get("pipeline_task")
    if existing is not None and not existing.done():
        logger.debug("Text submit ignored — pipeline already running")
        return
    state["mode"] = "processing"
    state["pipeline_task"] = asyncio.create_task(
        _run_text_pipeline(text, ws)
    )
    state["mode"] = "idle"
```

### 3. New `_run_text_pipeline(text, ws)`
Mirrors `_run_voice_pipeline_body`, but skips:
- audio concatenation, length check, STT call;
- `_t_audio_end` / `_t_stt_done` timing legs (emit `_t_stt_done = _t_audio_end = time.time()*1000` so the existing `turn_timing` waterfall still parses but shows STT=0 ms).

Reuses unchanged:
- `await broadcast_state("thinking")` after the user-turn broadcast;
- the existing `_orchestrator.handle(...)` / `_intent_parser` block;
- TTS broadcast + follow-up arming + `transcript` broadcast for the jarvis reply.

The user-turn broadcast happens up-front so the user immediately sees their own message echoed back:
```python
await _broadcast_transcript("user", text)
```
(extracting the inline JSON dump at line 250-260 into a small helper avoids drift between the two pipelines.)

### 4. `cancel_turn` already works
`_cancel_current_turn` cancels `state["pipeline_task"]` regardless of how it was started — no change needed.

---

## Edge cases
- **Submit while WS reconnecting**: `disabled` is true → input rejects. No queueing on the client side (avoid surprise sends after reconnect).
- **Submit while audio playing**: `disabled` is true (busy) — input is greyed. User must wait, same as today's voice path during TTS playback.
- **Very long input** (>4 000 chars): hard-trim on submit and emit a warning toast via the existing `notification` channel: `"Nachricht gekürzt — JARVIS verarbeitet maximal 4 000 Zeichen pro Eingabe."`.
- **Mixed mode within one turn**: user types a message, then mid-thinking presses the wake word. Treat as a regular new turn — `cancel_turn` the in-flight text turn first, then the voice turn takes over (existing barge-in semantics).
- **Whitespace / emoji-only input**: rejected client-side (trim → empty).
- **Backend unavailable**: `sendTranscript` no-ops when WS is closed; `disabled` already covers this case in the UI.
- **OpenClaw memory parity**: text turns must use the same conversation/session id as voice turns so memory recall is unaffected. Confirm by inspecting `_orchestrator.handle` — it's invoked the same way for both paths, so memory write happens regardless of input modality.

---

## Acceptance Criteria
1. In the expanded `TranscriptPanel`, a textarea is visible at the bottom and accepts focus.
2. Typing a message and pressing **Enter** clears the input, sends the text over WS, and within ≤500 ms the message appears as a `user` turn in the transcript (server-echoed, not client-appended).
3. JARVIS responds with the same orchestrator + TTS pipeline as voice — audio plays, jarvis transcript turn renders.
4. **Shift+Enter** inserts a newline and does not submit.
5. Whitespace-only / empty input does not submit (no WS frame sent).
6. Input is greyed and rejects submit while: WS disconnected, orb is `thinking`/`speaking`/`working`. Re-enables the moment orb returns to `idle` or `listening`.
7. STOP button cancels an in-flight text turn (no further audio, orb returns to idle, info notification appears).
8. Conversation memory shows the typed message in the next OpenClaw recall (same session id as voice turns).
9. Compact-mode `TranscriptPanel` is visually unchanged (no input row).
10. New unit tests:
    - `ChatInput.test.tsx`: Enter submits, Shift+Enter newlines, empty rejected, disabled blocks submit.
    - `useChatSubmit.test.ts`: `busy`/`disabled` derive correctly from orb state + connected flag.
    - `ws_server` test: `{"type":"transcript","text":"Hallo","isFinal":true}` triggers `_run_text_pipeline` (STT mocked / not called), broadcasts a `user` transcript, and reaches the orchestrator with the input text. Existing voice pipeline tests stay green.
11. `reviewer` returns `PASS`.

---

## Implementation Plan

### Step 1 — Backend: `transcript` command + text pipeline
- Extract user-turn broadcast helper from line 250-260.
- Add `_run_text_pipeline(text, ws)` mirroring `_run_voice_pipeline_body` minus STT.
- Add `_start_text_pipeline` and the `transcript` arm in `_handle_command`.
- Backend tests with mocked orchestrator/TTS.

### Step 2 — Frontend: `ChatInput` + `useChatSubmit`
- Implement `ChatInput.tsx` with auto-grow textarea, Enter/Shift+Enter, trim+clear.
- Implement `useChatSubmit.ts` deriving `busy`/`disabled` from `useWebSocket`.
- Vitest + RTL coverage.

### Step 3 — Wire into `TranscriptPanel`
- Render `<ChatInput/>` in `TranscriptExpanded` only.
- Update `TranscriptPanel.test.tsx` (input present in expanded, absent in compact, scroll-anchor still works).

### Step 4 — End-to-end smoke (manual)
- `python -m main` + `npm run dev` — type a message, observe round-trip, observe STOP, observe disable/enable transitions, observe memory recall on next voice turn.

### Step 5 — Reviewer
- `reviewer` agent reads spec + diff, expects `PASS`.
