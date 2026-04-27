# Template: `<name>Selectors.ts`

```ts
import { createSelector } from '@reduxjs/toolkit';
import type { RootState } from '@app/store';

export const select<Name>Data = (state: RootState) => state.<name>.data;
export const select<Name>HasLiveData = (state: RootState) => state.<name>.hasLiveData;
```
