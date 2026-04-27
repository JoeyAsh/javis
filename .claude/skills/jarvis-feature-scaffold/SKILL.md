---
name: jarvis-feature-scaffold
description: Emits the complete file layout and code templates for a new JARVIS frontend feature under src/features/<name>/. Use this when adding a new domain (a new panel, a new data source, etc.) so the feature ships rule-compliant by construction.
---

# JARVIS feature scaffold

When invoked with a feature name (e.g. `/jarvis-feature-scaffold mail`), emit the standard feature folder layout + file templates. The consumer (orchestrator or user) pastes into their workflow.

All paths below are relative to `frontend/src/`. Replace `<name>` with the lowercase feature name and `<Name>` with PascalCase.

---

## Folder tree

```
features/<name>/
├── components/
│   └── <Name>Panel/
│       ├── <Name>Panel.tsx
│       ├── <Name>Panel.types.ts
│       ├── __tests__/<Name>Panel.test.tsx
│       └── index.ts
├── hooks/
│   ├── use<Name>.ts
│   └── use<Name>.types.ts
├── <name>Api.ts
├── <name>Slice.ts
├── <name>Selectors.ts
├── types.ts
├── mock.ts
└── index.ts
```

Add helper components in sibling files (< 20 LOC) or sibling folders (≥ 20 LOC) under `components/`. Example: `components/<Name>Panel/<Name>Compact.tsx` + `<Name>Compact.types.ts`.

---

## File templates

### `types.ts`

```ts
/** Domain types + WS payloads for the <name> feature. */

export interface <Name>Payload {
    // ... server-pushed shape for the `<msg_type>` WS message
}
```

### `<name>Slice.ts`

```ts
import { createSlice, type PayloadAction } from '@reduxjs/toolkit';
import type { <Name>Payload } from './types';

export interface <Name>State {
    data: <Name>Payload | null;
    hasLiveData: boolean;
}

const initialState: <Name>State = {
    data: null,
    hasLiveData: false,
};

export const <name>Slice = createSlice({
    name: '<name>',
    initialState,
    reducers: {
        <name>DataReceived(state, action: PayloadAction<<Name>Payload>) {
            state.data = action.payload;
            state.hasLiveData = true;
        },
    },
});

export const { <name>DataReceived } = <name>Slice.actions;
export default <name>Slice.reducer;
```

### `<name>Api.ts`

```ts
import { baseApi } from '@core/api/baseApi';
import { wsClient } from '@core/websocket/wsClient';
import type { <Name>Payload } from './types';
import { <name>DataReceived } from './<name>Slice';

export const <name>Api = baseApi.injectEndpoints({
    endpoints: (builder) => ({
        stream<Name>: builder.query<null, void>({
            queryFn: () => ({ data: null }),
            async onCacheEntryAdded(_arg, { cacheDataLoaded, cacheEntryRemoved, dispatch }) {
                await cacheDataLoaded;
                const unsub = wsClient.subscribe<{ type: string; payload: <Name>Payload }>(
                    '<msg_type>',
                    (msg) => dispatch(<name>DataReceived(msg.payload)),
                );
                await cacheEntryRemoved;
                unsub();
            },
        }),
    }),
});

export const { useStream<Name>Query } = <name>Api;
```

### `<name>Selectors.ts`

```ts
import { createSelector } from '@reduxjs/toolkit';
import type { RootState } from '@app/store';

export const select<Name>Data = (state: RootState) => state.<name>.data;
export const select<Name>HasLiveData = (state: RootState) => state.<name>.hasLiveData;
```

### `hooks/use<Name>.types.ts`

```ts
import type { <Name>Payload } from '../types';

export interface Use<Name>Return {
    data: <Name>Payload | null;
    hasLiveData: boolean;
}
```

### `hooks/use<Name>.ts`

```ts
import { useAppSelector } from '@app';
import { useStream<Name>Query } from '../<name>Api';
import { select<Name>Data, select<Name>HasLiveData } from '../<name>Selectors';
import type { Use<Name>Return } from './use<Name>.types';

export function use<Name>(): Use<Name>Return {
    useStream<Name>Query();
    return {
        data: useAppSelector(select<Name>Data),
        hasLiveData: useAppSelector(select<Name>HasLiveData),
    };
}
```

### `components/<Name>Panel/<Name>Panel.types.ts`

```ts
import type { PanelMode } from '@common/types';

export interface <Name>PanelProps {
    mode?: PanelMode;
}
```

### `components/<Name>Panel/<Name>Panel.tsx`

```tsx
import type { ReactElement } from 'react';
import type { <Name>PanelProps } from './<Name>Panel.types';
import { use<Name> } from '../../hooks/use<Name>';

export function <Name>Panel({ mode = 'expanded' }: <Name>PanelProps): ReactElement {
    const { data, hasLiveData } = use<Name>();

    if (!hasLiveData) {
        return <div className="text-[var(--text-muted)] text-[10px] p-2">Loading…</div>;
    }

    return (
        <div className="flex flex-col gap-2 p-2">
            {/* TODO: render data */}
        </div>
    );
}

export default <Name>Panel;
```

### `components/<Name>Panel/index.ts`

```ts
export { <Name>Panel } from './<Name>Panel';
export type { <Name>PanelProps } from './<Name>Panel.types';
export { default } from './<Name>Panel';
```

### `components/<Name>Panel/__tests__/<Name>Panel.test.tsx`

```tsx
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { renderWithProviders } from '@test/renderWithProviders';
import { installMockWsClient } from '@test/mockWsClient';
import <name>Reducer, { <name>DataReceived } from '../../../<name>Slice';
import { <Name>Panel } from '../<Name>Panel';

vi.mock('@core/websocket/wsClient', () => import('@test/mockWsClient').then((m) => ({ wsClient: m._mockWsClientImpl })));

describe('<Name>Panel', () => {
    let ws: ReturnType<typeof installMockWsClient>;

    beforeEach(() => {
        ws = installMockWsClient();
    });

    it('renders loading state before first payload', () => {
        renderWithProviders(<<Name>Panel />, { reducers: { <name>: <name>Reducer } });
        expect(screen.getByText(/loading/i)).toBeInTheDocument();
    });

    it('renders data after <msg_type> payload arrives', () => {
        const { store } = renderWithProviders(<<Name>Panel />, { reducers: { <name>: <name>Reducer } });
        store.dispatch(<name>DataReceived({ /* mock payload */ }));
        // expect(...).toBeInTheDocument();
    });
});
```

### `mock.ts`

```ts
import type { <Name>Payload } from './types';

export const <name>Mock: <Name>Payload = {
    // fixture data
};
```

### `index.ts` (public barrel)

```ts
export { <Name>Panel } from './components/<Name>Panel';
export type { <Name>PanelProps } from './components/<Name>Panel';
export { use<Name> } from './hooks/use<Name>';
export type { Use<Name>Return } from './hooks/use<Name>.types';
export { default as <name>Reducer, <name>DataReceived } from './<name>Slice';
export type { <Name>Payload } from './types';
```

---

## Post-scaffold wiring

### 1. Register the slice in `app/store.ts`

```ts
import <name>Reducer from '@features/<name>/<name>Slice';

export const rootReducer = combineReducers({
    [baseApi.reducerPath]: baseApi.reducer,
    // ... other features
    <name>: <name>Reducer,
});
```

### 2. Add the panel to `app/panels.ts` (if it has a HUD panel)

```ts
import { <Name>Panel } from '@features/<name>';

export const PANELS: ReadonlyArray<PanelSpec> = [
    // ... other panels
    { id: '<name>', title: '<Name>', icon: '◇', homeSlot: 'L1', Component: <Name>Panel },
];
```

### 3. Add the WS message type to `core/websocket/types.ts`

```ts
import type { <Name>Payload } from '@features/<name>/types';

export type WsIncoming =
    // ... other messages
    | { type: '<msg_type>'; payload: <Name>Payload };
```

### 4. Verify

```bash
npx tsc --noEmit          # 0 errors
npm run test              # new tests pass
npm run build             # success
```

---

## Notes

- **Slice-less feature**: if the feature's only state is "the latest server payload" with no transient UI state, skip the slice and use RTK Query's cache directly: `builder.query<<Name>Payload | null, void>({ queryFn: () => ({ data: null }), onCacheEntryAdded: (_, { updateCachedData, cacheDataLoaded, cacheEntryRemoved }) => { ... updateCachedData(() => msg.payload) ... } })`. See `core/api/githubApi.ts` for the canonical example.
- **Feature without a panel**: features can be data-only (e.g. `@features/orbState`). Skip the `components/` folder and the panels-registry step.
- **Cross-feature imports are forbidden** — if two features share state, lift to `@common/*` or `@core/*`.
