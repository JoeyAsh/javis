import { useMemo } from 'react';
import type { ReactElement } from 'react';
import { systemMock } from '../../mock/systemMock';
import { useMockTicker, seededRand } from '../../mock/useMockTicker';
import type { SystemMetric, PanelMode } from '../../types';

export interface SystemPanelProps {
  metrics?: SystemMetric[];
  paused?: boolean;
  mode?: PanelMode;
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
      <path d={fill} fill={color} opacity={0.15} />
      <path d={path} fill="none" stroke={color} strokeWidth={1.2} />
    </svg>
  );
}

function useLiveMetrics(metrics: SystemMetric[], paused: boolean): SystemMetric[] {
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

function SystemCompact({ metrics }: { metrics: SystemMetric[] }): ReactElement {
  const cpu = metrics.find((m) => m.id === 'cpu');
  const ram = metrics.find((m) => m.id === 'ram');
  const net = metrics.find((m) => m.id === 'net');
  return (
    <>
      <div className="window-compact-row" style={{ gap: 10, fontSize: 11 }}>
        <span>
          <span className="mono-small" style={{ marginRight: 4 }}>CPU</span>
          <span style={{ color: 'var(--accent-bright)' }}>
            {cpu ? `${cpu.current.toFixed(0)}%` : '—'}
          </span>
        </span>
        <span>
          <span className="mono-small" style={{ marginRight: 4 }}>RAM</span>
          <span style={{ color: 'var(--accent-bright)' }}>
            {ram ? `${ram.current.toFixed(0)}%` : '—'}
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
            {net.current.toFixed(1)}↓
          </span>
          <span className="mono-small">Mb/s</span>
        </div>
      )}
    </>
  );
}

function SystemExpanded({ metrics }: { metrics: SystemMetric[] }): ReactElement {
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(3, 1fr)',
        gap: 10,
      }}
    >
      {metrics.map((m) => {
        const warn =
          (m.id === 'cpu' && m.current > 85) ||
          (m.id === 'cpuTemp' && m.current > 80) ||
          (m.id === 'ram' && m.current > 90);
        const color = warn ? 'var(--warning)' : 'var(--accent-bright)';
        return (
          <div key={m.id}>
            <div
              style={{
                display: 'flex',
                alignItems: 'baseline',
                justifyContent: 'space-between',
                marginBottom: 2,
              }}
            >
              <span className="mono-small" style={{ letterSpacing: 1 }}>
                {m.label}
              </span>
              <span
                style={{
                  fontSize: 12,
                  color,
                  fontWeight: 500,
                }}
              >
                {m.current.toFixed(m.id === 'net' ? 1 : 0)}
                <span style={{ fontSize: 9, color: 'var(--text-muted)', marginLeft: 2 }}>
                  {m.unit}
                </span>
              </span>
            </div>
            <Sparkline values={m.history} color={color} />
            {m.secondary !== undefined && (
              <div
                style={{
                  fontSize: 9,
                  color: 'var(--text-muted)',
                  letterSpacing: 1,
                  marginTop: 2,
                }}
              >
                {m.secondaryLabel} {m.secondary.toFixed(1)}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

export function SystemPanel({
  metrics = systemMock,
  paused = false,
  mode = 'expanded',
}: SystemPanelProps): ReactElement {
  const live = useLiveMetrics(metrics, paused);
  return mode === 'compact' ? <SystemCompact metrics={live} /> : <SystemExpanded metrics={live} />;
}

export default SystemPanel;
