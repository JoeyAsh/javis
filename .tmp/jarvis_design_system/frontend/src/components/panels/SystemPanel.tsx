import { useMemo } from 'react';
import type { ReactElement } from 'react';
import { systemMock } from '../../mock/systemMock';
import { useMockTicker, seededRand } from '../../mock/useMockTicker';
import { useSystemMetrics } from '../../hooks/useSystemMetrics';
import type { SystemMetricsLive, MetricHistories } from '../../hooks/useSystemMetrics';
import type { SystemMetric, PanelMode } from '../../types';

export interface SystemPanelProps {
  metrics?: SystemMetric[];
  paused?: boolean;
  mode?: PanelMode;
}

// Sparkline tile record — shared between mock and live render paths.
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

function Sparkline({ values, color }: { values: number[]; color: string }): ReactElement {
  const { path, fill } = useMemo(() => {
    const w = 100;
    const h = 24;
    if (values.length === 0) {
      return { path: '', fill: '' };
    }
    const max = Math.max(...values, 1);
    const step = w / Math.max(values.length - 1, 1);
    const pts = values.map((v, i) => {
      const x = i * step;
      const y = h - (v / max) * h;
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    });
    const line = `M ${pts.join(' L ')}`;
    const area = `${line} L ${w},${h} L 0,${h} Z`;
    return { path: line, fill: area };
  }, [values]);

  return (
    <svg
      viewBox="0 0 100 24"
      preserveAspectRatio="none"
      style={{ width: '100%', height: 24, display: 'block' }}
    >
      {path && <path d={fill} fill={color} opacity={0.15} />}
      {path && <path d={path} fill="none" stroke={color} strokeWidth={1.2} />}
    </svg>
  );
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

function liveToTiles(
  current: SystemMetricsLive,
  history: MetricHistories,
): SparkTile[] {
  return [
    {
      id: 'cpu',
      label: 'CPU',
      unit: '%',
      current: current.cpu,
      history: history.cpu,
    },
    {
      id: 'ram',
      label: 'RAM',
      unit: '%',
      current: current.ram,
      history: history.ram,
    },
    {
      id: 'gpu',
      label: 'GPU',
      unit: '%',
      current: current.gpu,
      history: history.gpu,
    },
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
    {
      id: 'disk',
      label: 'DISK',
      unit: '%',
      current: current.disk,
      history: history.disk,
    },
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
    <>
      <div className="window-compact-row" style={{ gap: 10, fontSize: 11 }}>
        <span>
          <span className="mono-small" style={{ marginRight: 4 }}>CPU</span>
          <span style={{ color: 'var(--accent-bright)' }}>
            {cpu?.current != null ? `${cpu.current.toFixed(0)}%` : '—'}
          </span>
        </span>
        <span>
          <span className="mono-small" style={{ marginRight: 4 }}>RAM</span>
          <span style={{ color: 'var(--accent-bright)' }}>
            {ram?.current != null ? `${ram.current.toFixed(0)}%` : '—'}
          </span>
        </span>
      </div>
      {net && (
        <div className="window-compact-row" style={{ fontSize: 10, color: 'var(--text-muted)' }}>
          <span className="mono-small">NET</span>
          <span style={{ color: 'var(--accent-bright)' }}>
            {(net.secondary ?? 0).toFixed(1)}↑
          </span>
          <span style={{ color: 'var(--accent-bright)' }}>
            {(net.current ?? 0).toFixed(1)}↓
          </span>
          <span className="mono-small">Mb/s</span>
        </div>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Expanded view
// ---------------------------------------------------------------------------

function SystemExpanded({ tiles }: { tiles: SparkTile[] }): ReactElement {
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(3, 1fr)',
        gap: 10,
      }}
    >
      {tiles.map((t) => {
        if (t.current === null) {
          return (
            <div key={t.id}>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'baseline',
                  justifyContent: 'space-between',
                  marginBottom: 2,
                }}
              >
                <span className="mono-small" style={{ letterSpacing: 1 }}>
                  {t.label}
                </span>
                <span
                  style={{
                    fontSize: 10,
                    color: 'var(--text-muted)',
                    fontStyle: 'italic',
                  }}
                >
                  n/a
                </span>
              </div>
              <div
                style={{
                  height: 24,
                  borderBottom: '1px dashed var(--border)',
                  opacity: 0.4,
                }}
              />
            </div>
          );
        }

        const warn =
          (t.id === 'cpu' && t.current > 85) ||
          (t.id === 'cpuTemp' && t.current > 80) ||
          (t.id === 'ram' && t.current > 90);
        const color = warn ? 'var(--warning)' : 'var(--accent-bright)';
        return (
          <div key={t.id}>
            <div
              style={{
                display: 'flex',
                alignItems: 'baseline',
                justifyContent: 'space-between',
                marginBottom: 2,
              }}
            >
              <span className="mono-small" style={{ letterSpacing: 1 }}>
                {t.label}
              </span>
              <span
                style={{
                  fontSize: 12,
                  color,
                  fontWeight: 500,
                }}
              >
                {t.current.toFixed(t.id === 'net' ? 1 : 0)}
                <span style={{ fontSize: 9, color: 'var(--text-muted)', marginLeft: 2 }}>
                  {t.unit}
                </span>
              </span>
            </div>
            <Sparkline values={t.history} color={color} />
            {t.secondary !== undefined && (
              <div
                style={{
                  fontSize: 9,
                  color: 'var(--text-muted)',
                  letterSpacing: 1,
                  marginTop: 2,
                }}
              >
                {t.secondaryLabel} {t.secondary.toFixed(1)}
              </div>
            )}
          </div>
        );
      })}
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
