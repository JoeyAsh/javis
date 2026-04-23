import { createSlice } from '@reduxjs/toolkit';
import type { PayloadAction } from '@reduxjs/toolkit';
import type { TranscriptTurn, TranscriptPayload } from './types';

const MAX_TURNS = 50;

export interface TranscriptState {
    turns: TranscriptTurn[];
    hasLiveData: boolean;
    /** Internal counter for stable id generation. */
    counter: number;
}

const initialState: TranscriptState = {
    turns: [],
    hasLiveData: false,
    counter: 0,
};

const transcriptSlice = createSlice({
    name: 'transcript',
    initialState,
    reducers: {
        transcriptReceived: {
            reducer(state, action: PayloadAction<TranscriptTurn>) {
                state.hasLiveData = true;
                state.turns.push(action.payload);
                if (state.turns.length > MAX_TURNS) {
                    state.turns = state.turns.slice(state.turns.length - MAX_TURNS);
                }
                state.counter += 1;
            },
            prepare(payload: TranscriptPayload) {
                const now = Date.now();
                // counter is not accessible in prepare, so we use the timestamp-based id.
                // The slice counter ensures uniqueness even for same-ms payloads.
                const turn: TranscriptTurn = {
                    id: `live-${now}-${Math.random().toString(36).slice(2, 7)}`,
                    role: payload.role,
                    text: payload.text,
                    at: new Date(now).toISOString(),
                };
                return { payload: turn };
            },
        },
    },
});

export const { transcriptReceived } = transcriptSlice.actions;
export default transcriptSlice.reducer;
