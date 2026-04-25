import { createSlice } from '@reduxjs/toolkit';
import type { PayloadAction } from '@reduxjs/toolkit';
import type { OrbState } from '@common/types';

export interface ActiveToolCall {
    name: string;
    summary: string;
}

export interface OrbStateState {
    base: OrbState;
    activeToolCall: ActiveToolCall | null;
    connected: boolean;
}

const initialState: OrbStateState = {
    base: 'idle',
    activeToolCall: null,
    connected: false,
};

export const orbStateSlice = createSlice({
    name: 'orbState',
    initialState,
    reducers: {
        orbStateReceived(state, action: PayloadAction<OrbState>) {
            state.base = action.payload;
        },
        toolCallStarted(
            state,
            action: PayloadAction<{ tool_name: string; summary: string }>,
        ) {
            state.activeToolCall = {
                name: action.payload.tool_name,
                summary: action.payload.summary,
            };
        },
        toolCallFinished(state) {
            state.activeToolCall = null;
        },
        connectionStateChanged(state, action: PayloadAction<boolean>) {
            state.connected = action.payload;
        },
    },
});

export const {
    orbStateReceived,
    toolCallStarted,
    toolCallFinished,
    connectionStateChanged,
} = orbStateSlice.actions;

export default orbStateSlice.reducer;
