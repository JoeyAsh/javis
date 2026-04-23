import { createSlice } from '@reduxjs/toolkit';
import type { PayloadAction } from '@reduxjs/toolkit';
import type { LogLinePayload, TurnTimingPayload } from './types';

export interface LogState {
    lines: LogLinePayload[];
    maxLines: number;
    turnTimings: TurnTimingPayload[];
    maxTurnTimings: number;
}

const DEFAULT_MAX_LINES = 500;
const DEFAULT_MAX_TURN_TIMINGS = 50;

const initialState: LogState = {
    lines: [],
    maxLines: DEFAULT_MAX_LINES,
    turnTimings: [],
    maxTurnTimings: DEFAULT_MAX_TURN_TIMINGS,
};

const logSlice = createSlice({
    name: 'log',
    initialState,
    reducers: {
        logLineReceived(state, action: PayloadAction<LogLinePayload>) {
            state.lines.push(action.payload);
            if (state.lines.length > state.maxLines) {
                state.lines = state.lines.slice(state.lines.length - state.maxLines);
            }
        },
        turnTimingReceived(state, action: PayloadAction<TurnTimingPayload>) {
            state.turnTimings.push(action.payload);
            if (state.turnTimings.length > state.maxTurnTimings) {
                state.turnTimings = state.turnTimings.slice(
                    state.turnTimings.length - state.maxTurnTimings,
                );
            }
        },
        logCleared(state) {
            state.lines = [];
        },
    },
});

export const { logLineReceived, turnTimingReceived, logCleared } = logSlice.actions;
export default logSlice.reducer;
