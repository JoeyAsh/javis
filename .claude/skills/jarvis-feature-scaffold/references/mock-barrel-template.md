# Templates: `mock.ts` and `index.ts` (public barrel)

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
