# Post-scaffold wiring steps

After generating the feature folder, wire it into the app layer.

## 1. Register the slice in `app/store.ts`

```ts
import <name>Reducer from '@features/<name>/<name>Slice';

export const rootReducer = combineReducers({
    [baseApi.reducerPath]: baseApi.reducer,
    // ... other features
    <name>: <name>Reducer,
});
```

## 2. Add the panel to `app/panels.ts` (if it has a HUD panel)

```ts
import { <Name>Panel } from '@features/<name>';

export const PANELS: ReadonlyArray<PanelSpec> = [
    // ... other panels
    { id: '<name>', title: '<Name>', icon: '◇', homeSlot: 'L1', Component: <Name>Panel },
];
```

## 3. Add the WS message type to `core/websocket/types.ts`

```ts
import type { <Name>Payload } from '@features/<name>/types';

export type WsIncoming =
    // ... other messages
    | { type: '<msg_type>'; payload: <Name>Payload };
```

## 4. Verify

```bash
npx tsc --noEmit          # 0 errors
npm run test              # new tests pass
npm run build             # success
```

## Notes

- **Slice-less feature**: if the feature's only state is "the latest server payload" with no transient UI state, skip the slice and use RTK Query's cache directly: `builder.query<<Name>Payload | null, void>({ queryFn: () => ({ data: null }), onCacheEntryAdded: (_, { updateCachedData, cacheDataLoaded, cacheEntryRemoved }) => { ... updateCachedData(() => msg.payload) ... } })`. See `core/api/githubApi.ts` for the canonical example.
- **Feature without a panel**: features can be data-only (e.g. `@features/orbState`). Skip the `components/` folder and the panels-registry step.
- **Cross-feature imports are forbidden** — if two features share state, lift to `@common/*` or `@core/*`.
