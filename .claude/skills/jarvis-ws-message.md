---
name: jarvis-ws-message
description: End-to-end checklist for adding a new WebSocket message type to JARVIS — backend broadcast + frontend subscription + slice action + tests on both sides.
---

# JARVIS new-WS-message-type checklist

When adding a new server → client (or client → server) WS message, follow this 13-step checklist. It ensures the payload type, broadcast call, subscription, slice action, and tests on both sides are all wired consistently.

Terminology:
- `<msg_type>` — the string discriminator on the WS envelope (e.g. `"mail_state"`, `"barge_in"`)
- `<Name>` — PascalCase feature owner (e.g. `Mail`, `BargeIn`)
- `<name>` — lowercase feature folder (e.g. `mail`)
- `<Payload>` — the TS interface name for the message payload

---

## Backend (Python, aiohttp)

### 1. Define the payload model

In the owning backend module (e.g. `src/integrations/google/mail.py` for a mail-related message, or `src/brain/orb.py` for an orb-state message), define a Pydantic / dataclass model:

```python
from pydantic import BaseModel

class <Name>Payload(BaseModel):
    # fields matching the TS interface exactly
    ...
```

### 2. Broadcast call

In the producer code (poller, event handler, lifecycle hook):

```python
from api.ws_server import broadcast_ws_message

await broadcast_ws_message({
    "type": "<msg_type>",
    "payload": payload.model_dump(),
})
```

Use the existing broadcast helper — don't instantiate a WS client locally.

### 3. Log the broadcast

```python
logger.debug(f"<msg_type> broadcast: {summary_of_payload(payload)}")
```

Use `loguru`'s `logger.debug()` for per-broadcast tracing; `logger.info()` for lifecycle events (start/stop of the producer).

### 4. Pytest test

`tests/test_<module>.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_<feature>_broadcasts_<msg_type>():
    with patch("api.ws_server.broadcast_ws_message", new=AsyncMock()) as mock_broadcast:
        await trigger_the_producer(...)
        mock_broadcast.assert_awaited_once()
        call = mock_broadcast.await_args[0][0]
        assert call["type"] == "<msg_type>"
        assert call["payload"]["<field>"] == expected_value
```

---

## Frontend (TypeScript, React, RTK Query)

### 5. Payload type in the feature's `types.ts`

`frontend/src/features/<name>/types.ts`:

```ts
export interface <Name>Payload {
    // fields matching the Python model
}
```

### 6. Extend `WsIncoming` union in `core/websocket/types.ts`

```ts
import type { <Name>Payload } from '@features/<name>/types';

export type WsIncoming =
    | ... // existing variants
    | { type: '<msg_type>'; payload: <Name>Payload };
```

Re-export `<Name>Payload` from `core/websocket/types.ts` if other infrastructure code consumes it.

### 7. Subscribe in the feature's `<name>Api.ts`

```ts
onCacheEntryAdded: async (_arg, { cacheDataLoaded, cacheEntryRemoved, dispatch }) => {
    await cacheDataLoaded;
    const unsub = wsClient.subscribe<{ type: string; payload: <Name>Payload }>(
        '<msg_type>',
        (msg) => dispatch(<name>PayloadReceived(msg.payload)),
    );
    await cacheEntryRemoved;
    unsub();
},
```

If the feature already has a streaming query, add a second `wsClient.subscribe` call inside the same `onCacheEntryAdded` — don't create a second query unless the message belongs to a different feature.

### 8. Slice action in `<name>Slice.ts`

```ts
<name>PayloadReceived(state, action: PayloadAction<<Name>Payload>) {
    state.someField = action.payload.someField;
    // update related state
},
```

If the payload represents transient state that should flush on unmount, add a companion `<name>Cleared()` action.

### 9. Mock fixture in `<name>/mock.ts`

```ts
import type { <Name>Payload } from './types';

export const <name>PayloadMock: <Name>Payload = {
    // fixture values
};
```

### 10. Vitest integration test using `mockWsClient`

`__tests__/<name>Api.test.ts` OR the panel component test:

```ts
import { installMockWsClient } from '@test/mockWsClient';
import <name>Reducer from '../<name>Slice';
import { select<Name>SomeField } from '../<name>Selectors';

const ws = installMockWsClient();

it('updates slice state when <msg_type> arrives', async () => {
    const { store } = renderWithProviders(<<Name>Panel />, { reducers: { <name>: <name>Reducer } });
    await waitFor(() => expect(ws.subscribers('<msg_type>')).toBe(1));
    ws.emit('<msg_type>', { /* mock payload */ });
    expect(select<Name>SomeField(store.getState())).toBe(expected);
});
```

### 11. Slice unit test (pure reducer)

`__tests__/<name>Slice.test.ts`:

```ts
import <name>Reducer, { <name>PayloadReceived } from '../<name>Slice';

it('<name>PayloadReceived updates state', () => {
    const next = <name>Reducer(undefined, <name>PayloadReceived({ /* payload */ }));
    expect(next.someField).toBe(expected);
});
```

### 12. Selector test (if memoized)

```ts
it('select<Name>SomeField returns stable reference for identical state', () => {
    const a = { ... };
    const b = { ...a }; // same content
    expect(select<Name>SomeField(a)).toBe(select<Name>SomeField(a)); // memoized hit
});
```

### 13. Docs

If the message introduces a new user-visible feature, update `docs/FRONTEND.md` § WebSocket Protocol and `docs/ARCHITECTURE.md` § Data flow. For minor internal messages (e.g. tool-call lifecycle), skip.

---

## Verification

Run all of these locally before committing:

```bash
# Backend
pytest tests/test_<module>.py

# Frontend
cd frontend
npx tsc --noEmit
npm run test
npm run build
```

## Client → server messages

The checklist above is for server → client. For client → server messages:
- Skip steps 1-4 (no Pydantic model, no broadcast) — instead add the message to `WsOutgoing` union and define the input validation in the `api/ws_server.py` handler.
- Step 6 becomes `WsOutgoing` extension.
- Steps 7-12 become a one-way send helper in `core/websocket/commands.ts` (e.g. `sendFooCommand(value)`), plus the slice action optimistically updating state.
- Step 10 tests that the command is sent via `wsClient.send` with the correct payload.
