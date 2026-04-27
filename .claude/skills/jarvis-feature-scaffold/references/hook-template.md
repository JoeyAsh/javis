# Templates: `hooks/use<Name>.types.ts` and `hooks/use<Name>.ts`

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
