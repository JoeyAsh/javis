import { seededRand } from '@common/hooks/useMockTicker';
import type { SystemMetricsLive, MetricHistories, SystemMetric } from '../../types';
import type { SparkTile } from '../SystemTile';

export function driftHistory(base: number[], tick: number, seedBase: number): number[] {
    return base.map((v, i) => {
        const jitter = (seededRand(seedBase + tick + i) - 0.5) * 8;
        return Math.max(0, Math.min(100, v + jitter));
    });
}

export function liveToTiles(current: SystemMetricsLive, history: MetricHistories): SparkTile[] {
    return [
        { id: 'cpu', label: 'CPU', unit: '%', current: current.cpu, history: history.cpu },
        { id: 'ram', label: 'RAM', unit: '%', current: current.ram, history: history.ram },
        { id: 'gpu', label: 'GPU', unit: '%', current: current.gpu, history: history.gpu },
        {
            id: 'cpuTemp',
            label: 'CPU TEMP',
            unit: '°C',
            current: current.cpuTemp,
            history: history.cpuTemp,
        },
        {
            id: 'net',
            label: 'NET',
            unit: 'Mb/s',
            current: current.netDown,
            history: history.netDown,
            secondary: current.netUp,
            secondaryLabel: 'UP',
        },
        { id: 'disk', label: 'DISK', unit: '%', current: current.disk, history: history.disk },
    ];
}

export function mockToTiles(metrics: SystemMetric[]): SparkTile[] {
    return metrics.map((m) => ({
        id: m.id,
        label: m.label,
        unit: m.unit,
        current: m.current,
        history: m.history,
        secondary: m.secondary,
        secondaryLabel: m.secondaryLabel,
    }));
}
