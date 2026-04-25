import { useMemo } from 'react';
import { useMockTicker, seededRand } from '@common/hooks/useMockTicker';
import type { SystemMetric } from '../../types';
import { driftHistory } from './utils';

/** Ticks mock metrics forward with seeded random jitter. */
export function useLiveMockMetrics(metrics: SystemMetric[], paused: boolean): SystemMetric[] {
    const tick = useMockTicker(1500, paused);
    return useMemo<SystemMetric[]>(
        () =>
            metrics.map((m, idx) => ({
                ...m,
                current: Math.max(
                    0,
                    Math.min(
                        m.id === 'cpuTemp' ? 95 : 100,
                        m.current + (seededRand(tick + idx * 7) - 0.5) * 6,
                    ),
                ),
                history: driftHistory(m.history, tick, idx * 11),
            })),
        [metrics, tick],
    );
}
