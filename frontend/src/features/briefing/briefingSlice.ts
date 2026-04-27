import { createSlice } from '@reduxjs/toolkit';
import type { PayloadAction } from '@reduxjs/toolkit';
import type { BriefingState, BriefingPayload } from './types';

const initialState: BriefingState = {
    payload: null,
    receivedAt: null,
};

const briefingSlice = createSlice({
    name: 'briefing',
    initialState,
    reducers: {
        briefingReceived(state, action: PayloadAction<BriefingPayload>) {
            state.payload = action.payload;
            state.receivedAt = new Date().toISOString();
        },
        briefingCleared(state) {
            state.payload = null;
            state.receivedAt = null;
        },
    },
});

export const { briefingReceived, briefingCleared } = briefingSlice.actions;
export default briefingSlice.reducer;
