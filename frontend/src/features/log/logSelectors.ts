import type { RootState } from '@app';
import type { LogLinePayload, TurnTimingPayload } from './types';

export function selectLogLines(state: RootState): LogLinePayload[] {
    return state.log.lines;
}

export function selectTurnTimings(state: RootState): TurnTimingPayload[] {
    return state.log.turnTimings;
}
