import type { RootState } from '@app';
import type { SystemMetricsLive, MetricHistories } from './types';

export function selectSystemLive(state: RootState): SystemMetricsLive | null {
    return state.system.live;
}

export function selectSystemHistories(state: RootState): MetricHistories {
    return state.system.histories;
}

export function selectSystemHasLiveData(state: RootState): boolean {
    return state.system.hasLiveData;
}
