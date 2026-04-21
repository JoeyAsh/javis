/**
 * SystemPanel — panel body for system metrics.
 * Returns only body content; the Window wrapper supplies chrome via HudPanel.
 *
 * Prototype reference: SystemPanel() in JARVIS HUD Hypermodern.html
 * Renders a 3-column tile grid (expanded) or a compact summary row.
 */
import { useMemo } from 'react';
import type { ReactElement } from 'react';
import { systemMock } from '../../../mock/systemMock';
import { useMockTicker, seededRand } from '../../../mock/useMockTicker';
import { useSystemMetrics } from '../../../hooks/useSystemMetrics';
import type { SystemMetricsLive, MetricHistories } from '../../../hooks/useSystemMetrics';
import type { SystemMetric, PanelMode } from '../../../types';
import { SystemTile } from './SystemTile';
import type { SparkTile } from './SystemTile';
import './SystemPanel.css';

export interface SystemPanelProps {
  metrics?: SystemMetric[];
  paused?: boolean;
  mode?: PanelMode;
}

// ---------------------------------------------------------------------------
// Helpers
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

function SystemCompact({ tiles }: { tiles: SparkTile[] }): ReactElement {
  const cpu = tiles.find((t) => t.id === 'cpu');
  const ram = tiles.find((t) => t.id === 'ram');
  const net = tiles.find((t) => t.id === 'net');

  return (
    <div className="system-compact">
      <div className="system-compact__row">
        <span className="system-compact__metric">
          <span className="system-compact__metric-label">CPU</span>
          <span className="system-compact__metric-value">
            {cpu?.current != null ? `${cpu.current.toFixed(0)}%` : '—'}
          </span>
        </span>
        <span className="system-compact__metric">
          <span className="system-compact__metric-label">RAM</span>
          <span className="system-compact__metric-value">
            {ram?.current != null ? `${ram.current.toFixed(0)}%` : '—'}
          </span>
        </span>
      </div>
      {net && (
        <div className="system-compact__net">
          <span className="system-compact__metric-label">NET</span>
          <span className="system-compact__metric-value">
            {(net.secondary ?? 0).toFixed(1)}↑
          </span>
          <span className="system-compact__metric-value">
            {(net.current ?? 0).toFixed(1)}↓
          </span>
          <span className="system-compact__metric-label">Mb/s</span>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Expanded view
// ---------------------------------------------------------------------------

function SystemExpanded({ tiles }: { tiles: SparkTile[] }): ReactElement {
  return (
    <div className="system-panel">
      <div className="system-tiles">
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
  const { current, history, isLive } = useSystemMetrics();
  const mockTiles = useLiveMockMetrics(metrics, paused);

  const tiles: SparkTile[] = useMemo(() => {
    if (isLive && current) {
      return liveToTiles(current, history);
    }
    return mockToTiles(mockTiles);
  }, [isLive, current, history, mockTiles]);

  return mode === 'compact' ? (
    <SystemCompact tiles={tiles} />
  ) : (
    <SystemExpanded tiles={tiles} />
  );
}

export default SystemPanel;
