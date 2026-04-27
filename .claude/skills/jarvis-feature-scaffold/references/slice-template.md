# Template: `<name>Slice.ts`

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
