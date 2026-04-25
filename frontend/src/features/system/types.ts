/**
 * System feature types.
 */

/**
 * Live system metrics payload from the backend.
 *
 * `cpu`, `mem`, `uptime` are required (legacy-compatible). The remaining
 * fields may be `null` if the host doesn't expose that sensor.
 */
export interface SystemMetricsPayload {
    cpu: number;
    mem: number;
    uptime: string;
    gpu?: number | null;
    cpu_temp?: number | null;
    net_up?: number;
    net_down?: number;
    disk?: number;
}

/** Legacy mock metric shape used by system mock data only. */
export interface SystemMetric {
    id: 'cpu' | 'ram' | 'gpu' | 'cpuTemp' | 'net' | 'disk';
    label: string;
    unit: string;
    current: number;
    history: number[];
    secondary?: number;
    secondaryLabel?: string;
}

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
