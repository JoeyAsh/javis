import type { LogLinePayload, TurnTimingPayload } from '../types';

export interface UseLogReturn {
    lines: ReadonlyArray<LogLinePayload>;
    turnTimings: ReadonlyArray<TurnTimingPayload>;
    loading: boolean;
    clear: () => void;
}
