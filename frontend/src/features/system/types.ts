export type MetricKey = 'cpu' | 'ram' | 'gpu' | 'cpuTemp' | 'netUp' | 'netDown' | 'disk';

/** History buffer length per metric channel. */
export const METRIC_HISTORY_LENGTH = 60;

export const METRIC_KEYS: readonly MetricKey[] = [
    'cpu',
    'ram',
    'gpu',
    'cpuTemp',
    'netUp',
    'netDown',
    'disk',
] as const;

/**
 * Live-metrics snapshot kept in Redux state. Normalises field names to
 * camelCase as used by the rest of the frontend.
 */
export interface SystemMetricsLive {
    cpu: number;
    ram: number;
    gpu: number | null;
    cpuTemp: number | null;
    netUp: number;
    netDown: number;
    disk: number;
    uptime: string;
}

export type MetricHistories = Record<MetricKey, number[]>;
