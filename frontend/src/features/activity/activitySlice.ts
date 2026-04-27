import { createSlice } from '@reduxjs/toolkit';
import type { PayloadAction } from '@reduxjs/toolkit';
import type { NarrationItem, NarrationEngineState, SourceEntry, NarrationStatePayload, ActivityPanelPayload } from './types';

const MAX_HISTORY = 20;

export interface ActivityState {
    /** Current engine state from `narration_state` messages. */
    state: NarrationEngineState;
    /** ISO 8601 quiet-until timestamp, or null when quiet mode is off. */
    quietUntil: string | null;
    /** Per-source status map from `activity_panel` messages. */
    sources: Record<string, SourceEntry>;
    /** Narration history — newest first, capped at MAX_HISTORY. */
    history: NarrationItem[];
    /** True once any live WS data has arrived. */
    hasLiveData: boolean;
}

const initialState: ActivityState = {
    state: 'idle',
    quietUntil: null,
    sources: {},
    history: [],
    hasLiveData: false,
};

const activitySlice = createSlice({
    name: 'activity',
    initialState,
    reducers: {
        narrationStateReceived(state, action: PayloadAction<NarrationStatePayload>) {
            state.hasLiveData = true;
            state.state = action.payload.state;
            state.quietUntil = action.payload.quiet_until;
            // Merge incoming items into history, dedup by id, newest first, cap at max.
            const incomingIds = new Set(action.payload.items.map((i) => i.id));
            const existing = state.history.filter((i) => !incomingIds.has(i.id));
            const merged = [...action.payload.items, ...existing];
            state.history = merged.length > MAX_HISTORY ? merged.slice(0, MAX_HISTORY) : merged;
        },
        activityPanelReceived(state, action: PayloadAction<ActivityPanelPayload>) {
            state.hasLiveData = true;
            state.sources = action.payload.sources;
            // Merge history — dedup by id, newest first, cap at max.
            const incomingIds = new Set(action.payload.history.map((i) => i.id));
            const existing = state.history.filter((i) => !incomingIds.has(i.id));
            const merged = [...action.payload.history, ...existing];
            state.history = merged.length > MAX_HISTORY ? merged.slice(0, MAX_HISTORY) : merged;
        },
    },
});

export const { narrationStateReceived, activityPanelReceived } = activitySlice.actions;
export default activitySlice.reducer;
