/**
 * SystemView — system metrics panel content using lib primitives.
 *
 * Replaces legacy components/panels/System/SystemPanel.tsx.
 * Uses lib Metric, Sparkline, Label for display.
 */
import { useMemo } from 'react';
import type { ReactElement } from 'react';
import { Label, Metric, Sparkline } from '../lib';
import { systemMock } from '../mock/systemMock';
import { useMockTicker, seededRand } from '../mock/useMockTicker';
import { useSystemMetrics } from '../hooks/useSystemMetrics';
import type { SystemMetricsLive, MetricHistories } from '../hooks/useSystemMetrics';
import type { SystemMetric, PanelMode } from '../types';
import './SystemView.css';

export interface SystemViewProps {
    metrics?: SystemMetric[];
    paused?: boolean;
    mode?: PanelMode;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

interface SparkTile {
    id: SystemMetric['id'];
    label: string;
    unit: string;
    current: number | null;
    history: number[];
    secondary?: number;
    secondaryLabel?: string;
}

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

function isWarn(tile: SparkTile): boolean {
    if (tile.current === null) return false;
    return (
        (tile.id === 'cpu' && tile.current > 85) ||
        (tile.id === 'cpuTemp' && tile.current > 80) ||
        (tile.id === 'ram' && tile.current > 90)
    );
}

// ── Tile (uses lib Metric + Sparkline) ───────────────────────────────────────

function SystemTile({ tile }: { tile: SparkTile }): ReactElement {
    const warn = isWarn(tile);
    const precision = tile.id === 'net' ? 1 : 0;

    if (tile.current === null) {
        return (
            <div className="sys-tile">
                <div className="sys-tile__hdr">
                    <Label>{tile.label}</Label>
                    <Metric value="n/a" small />
                </div>
                <div className="sys-tile__na" />
            </div>
        );
    }

    return (
        <div className={`sys-tile${warn ? ' sys-tile--warn' : ''}`}>
            <div className="sys-tile__hdr">
                <Label>{tile.label}</Label>
                <Metric value={tile.current.toFixed(precision)} unit={tile.unit} warn={warn} />
            </div>
            <Sparkline
                data={tile.history}
                variant={warn ? 'warn' : 'accent'}
                height={24}
                aria-label={`${tile.label} sparkline`}
            />
            {tile.secondary !== undefined && (
                <div className="sys-tile__sub">
                    <Label dim>{tile.secondaryLabel}</Label>{' '}
                    <Metric value={tile.secondary.toFixed(1)} small />
                </div>
            )}
        </div>
    );
}

// ── Compact ──────────────────────────────────────────────────────────────────

function SystemCompact({ tiles }: { tiles: SparkTile[] }): ReactElement {
    const cpu = tiles.find((t) => t.id === 'cpu');
    const ram = tiles.find((t) => t.id === 'ram');
    const net = tiles.find((t) => t.id === 'net');

    return (
        <div className="sys-compact">
            <div className="sys-compact__row">
                <span className="sys-compact__metric">
                    <Label>CPU</Label>
                    <Metric
                        value={cpu?.current != null ? `${cpu.current.toFixed(0)}%` : '—'}
                        small
                    />
                </span>
                <span className="sys-compact__metric">
                    <Label>RAM</Label>
                    <Metric
                        value={ram?.current != null ? `${ram.current.toFixed(0)}%` : '—'}
                        small
                    />
                </span>
            </div>
            {net && (
                <div className="sys-compact__net">
                    <Label>NET</Label>
                    <Metric value={`${(net.secondary ?? 0).toFixed(1)}↑`} small />
                    <Metric value={`${(net.current ?? 0).toFixed(1)}↓`} small />
                    <Label dim>Mb/s</Label>
                </div>
            )}
        </div>
    );
}

// ── Expanded ─────────────────────────────────────────────────────────────────

function SystemExpanded({ tiles }: { tiles: SparkTile[] }): ReactElement {
    return (
        <div className="sys-expanded">
            <div className="sys-tiles">
                {tiles.map((t) => (
                    <SystemTile key={t.id} tile={t} />
                ))}
            </div>
        </div>
    );
}

// ── Entry point ──────────────────────────────────────────────────────────────

export function SystemView({
    metrics = systemMock,
    paused = false,
    mode = 'expanded',
}: SystemViewProps): ReactElement {
    const { current, history, isLive } = useSystemMetrics();
    const mockTiles = useLiveMockMetrics(metrics, paused);

    const tiles: SparkTile[] = useMemo(() => {
        if (isLive && current) {
            return liveToTiles(current, history);
        }
        return mockToTiles(mockTiles);
    }, [isLive, current, history, mockTiles]);

    return mode === 'compact' ? <SystemCompact tiles={tiles} /> : <SystemExpanded tiles={tiles} />;
}

export default SystemView;

