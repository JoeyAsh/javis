import { useMemo } from 'react';
import type { ReactElement } from 'react';
import { systemMock } from '../../mock';
import { useSystem } from '../../hooks/useSystem';
import { SystemTile } from '../SystemTile';
import type { SparkTile } from '../SystemTile';
import type { SystemPanelProps, SystemCompactProps, SystemExpandedProps } from './SystemPanel.types';
import { useLiveMockMetrics } from './useLiveMockMetrics';
import { liveToTiles, mockToTiles } from './utils';
import styles from './SystemPanel.module.css';

// ---------------------------------------------------------------------------
// Compact view
// ---------------------------------------------------------------------------

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
