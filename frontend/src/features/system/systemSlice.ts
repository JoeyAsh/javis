import { createSlice } from '@reduxjs/toolkit';
import type { PayloadAction } from '@reduxjs/toolkit';
import type { SystemMetricsPayload } from './types';
import type { SystemMetricsLive, MetricHistories, MetricKey } from './types';
import { METRIC_HISTORY_LENGTH } from './types';

export interface SystemState {
    live: SystemMetricsLive | null;
    histories: MetricHistories;
    hasLiveData: boolean;
}

function emptyHistories(): MetricHistories {
    return {
        cpu: [],
        ram: [],
        gpu: [],
        cpuTemp: [],
        netUp: [],
        netDown: [],
        disk: [],
    };
}

function toLive(payload: SystemMetricsPayload): SystemMetricsLive {
    return {
        cpu: payload.cpu,
        ram: payload.mem,
        gpu: payload.gpu ?? null,
        cpuTemp: payload.cpu_temp ?? null,
        netUp: payload.net_up ?? 0,
        netDown: payload.net_down ?? 0,
        disk: payload.disk ?? 0,
        uptime: payload.uptime,
    };
}

/** Push a value onto a ring buffer. Null/NaN values are skipped. */
function pushHistory(buf: number[], value: number | null, limit: number): number[] {
    if (value === null || Number.isNaN(value)) return buf;
    const next = buf.length >= limit ? buf.slice(buf.length - limit + 1) : buf.slice();
    next.push(value);
    return next;
}

const initialState: SystemState = {
    live: null,
    histories: emptyHistories(),
    hasLiveData: false,
};

const systemSlice = createSlice({
    name: 'system',
    initialState,
    reducers: {
        systemMetricsReceived(state, action: PayloadAction<SystemMetricsPayload>) {
            const live = toLive(action.payload);
            state.live = live;
            state.hasLiveData = true;

            const keys: MetricKey[] = [
                'cpu',
                'ram',
                'gpu',
                'cpuTemp',
                'netUp',
                'netDown',
                'disk',
            ];

            const values: Record<MetricKey, number | null> = {
                cpu: live.cpu,
                ram: live.ram,
                gpu: live.gpu,
                cpuTemp: live.cpuTemp,
                netUp: live.netUp,
                netDown: live.netDown,
                disk: live.disk,
            };

            for (const key of keys) {
                state.histories[key] = pushHistory(
                    state.histories[key],
                    values[key],
                    METRIC_HISTORY_LENGTH,
                );
            }
        },
    },
});

export const { systemMetricsReceived } = systemSlice.actions;
export default systemSlice.reducer;
