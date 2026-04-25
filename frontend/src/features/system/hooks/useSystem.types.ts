import type { SystemMetricsLive, MetricHistories } from '../types';

export interface UseSystemReturn {
    live: SystemMetricsLive | null;
    histories: MetricHistories;
    hasLiveData: boolean;
    loading: boolean;
}
