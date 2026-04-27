# Templates: `components/<Name>Panel/` files

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
