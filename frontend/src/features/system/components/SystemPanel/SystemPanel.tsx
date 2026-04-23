import { useMemo } from 'react';
import type { ReactElement } from 'react';
import { useMockTicker, seededRand } from '@common/hooks/useMockTicker';
import { systemMock } from '../../mock';
import { useSystem } from '../../hooks/useSystem';
import type { SystemMetricsLive, MetricHistories } from '../../types';
import type { SystemMetric } from '../../../../types';
import { SystemTile } from '../SystemTile';
import type { SparkTile } from '../SystemTile';
import type { SystemPanelProps } from './SystemPanel.types';
import styles from './SystemPanel.module.css';

// ---------------------------------------------------------------------------
// Local mock-ticker hook (< 50 LOC inline)
// ---------------------------------------------------------------------------

function driftHistory(base: number[], tick: number, seedBase: number): number[] {
    return base.map((v, i) => {
        const jitter = (seededRand(seedBase + tick + i) - 0.5) * 8;
        return Math.max(0, Math.min(100, v + jitter));
    });
}

function useLiveMockMetrics(metrics: SystemMetric[], paused: boolean): SystemMetric[] {
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

// ---------------------------------------------------------------------------
// Tile conversion helpers
// ---------------------------------------------------------------------------

function liveToTiles(current: SystemMetricsLive, history: MetricHistories): SparkTile[] {
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

function mockToTiles(metrics: SystemMetric[]): SparkTile[] {
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

// ---------------------------------------------------------------------------
// Compact view
// ---------------------------------------------------------------------------

interface SystemCompactProps {
    tiles: SparkTile[];
}

function SystemCompact({ tiles }: SystemCompactProps): ReactElement {
    const cpu = tiles.find((t) => t.id === 'cpu');
    const ram = tiles.find((t) => t.id === 'ram');
    const net = tiles.find((t) => t.id === 'net');

    return (
        <div className={styles.compact}>
            <div className={styles.compactRow}>
                <span className={styles.compactMetric}>
                    <span className={styles.metricLabel}>CPU</span>
                    <span className={styles.metricValue}>
                        {cpu?.current != null ? `${cpu.current.toFixed(0)}%` : '—'}
                    </span>
                </span>
                <span className={styles.compactMetric}>
                    <span className={styles.metricLabel}>RAM</span>
                    <span className={styles.metricValue}>
                        {ram?.current != null ? `${ram.current.toFixed(0)}%` : '—'}
                    </span>
                </span>
            </div>
            {net && (
                <div className={styles.compactNet}>
                    <span className={styles.metricLabel}>NET</span>
                    <span className={styles.metricValue}>
                        {(net.secondary ?? 0).toFixed(1)}↑
                    </span>
                    <span className={styles.metricValue}>
                        {(net.current ?? 0).toFixed(1)}↓
                    </span>
                    <span className={styles.metricLabel}>Mb/s</span>
                </div>
            )}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Expanded view
// ---------------------------------------------------------------------------

interface SystemExpandedProps {
    tiles: SparkTile[];
}

function SystemExpanded({ tiles }: SystemExpandedProps): ReactElement {
    return (
        <div className={styles.panel}>
            <div className={styles.tiles}>
                {tiles.map((t) => (
                    <SystemTile key={t.id} tile={t} />
                ))}
            </div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

export function SystemPanel({
    metrics = systemMock,
    paused = false,
    mode = 'expanded',
}: SystemPanelProps): ReactElement {
    const { live, histories, hasLiveData } = useSystem();
    const mockTiles = useLiveMockMetrics(metrics, paused);

    const tiles: SparkTile[] = useMemo(() => {
        if (hasLiveData && live) {
            return liveToTiles(live, histories);
        }
        return mockToTiles(mockTiles);
    }, [hasLiveData, live, histories, mockTiles]);

    return mode === 'compact' ? <SystemCompact tiles={tiles} /> : <SystemExpanded tiles={tiles} />;
}

export default SystemPanel;
