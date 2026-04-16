import { useEffect, useRef, useState } from 'react';
import { subscribeSystemMetrics } from './useWebSocket';
import type { SystemMetricsPayload } from '../types';

/** Numeric metric channels that drive the SystemPanel sparklines. */
export type MetricKey = 'cpu' | 'ram' | 'gpu' | 'cpuTemp' | 'netUp' | 'netDown' | 'disk';

/** History buffer length per metric. */
export const METRIC_HISTORY_LENGTH = 30;

const METRIC_KEYS: readonly MetricKey[] = [
  'cpu',
  'ram',
  'gpu',
  'cpuTemp',
  'netUp',
  'netDown',
  'disk',
] as const;

/**
 * Live-metrics snapshot kept in React state. Mirrors the backend
 * {@link SystemMetricsPayload} but normalises field names to the
 * camelCase used by the rest of the frontend.
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

export interface UseSystemMetricsReturn {
  current: SystemMetricsLive | null;
  history: MetricHistories;
  isLive: boolean;
}

const emptyHistories = (): MetricHistories => ({
  cpu: [],
  ram: [],
  gpu: [],
  cpuTemp: [],
  netUp: [],
  netDown: [],
  disk: [],
});

function toLive(payload: SystemMetricsPayload): SystemMetricsLive {
  return {
    cpu: payload.cpu,
    ram: payload.mem,
    gpu: payload.gpu ?? null,
    cpuTemp: payload.cpu_temp ?? null,
    netUp: payload.net_up ?? 0,
    netDown: payload.net_down ?? 0,
    disk: payload.disk ?? 0,
    uptime: payload.uptime,
  };
}

/**
 * Push a value onto a rolling buffer without mutating the input.
 * `null` values are skipped so sparklines for unavailable sensors stay
 * flat (or empty) rather than polluting the series with zeroes.
 */
function pushHistory(
  buf: number[],
  value: number | null,
  limit: number,
): number[] {
  if (value === null || Number.isNaN(value)) return buf;
  const next = buf.length >= limit ? buf.slice(buf.length - limit + 1) : buf.slice();
  next.push(value);
  return next;
}

/**
 * Subscribe to the backend `system` WebSocket broadcast.
 *
 * Maintains per-metric rolling history buffers for sparkline rendering.
 * When the tab is hidden (`document.hidden`), the latest `current`
 * value is still tracked but history updates are paused so background
 * tabs don't burn through memory / re-renders.
 */
export function useSystemMetrics(): UseSystemMetricsReturn {
  const [current, setCurrent] = useState<SystemMetricsLive | null>(null);
  const [history, setHistory] = useState<MetricHistories>(emptyHistories);
  const [isLive, setIsLive] = useState(false);

  const hiddenRef = useRef<boolean>(
    typeof document === 'undefined' ? false : document.hidden,
  );

  useEffect(() => {
    const onVisibility = (): void => {
      hiddenRef.current = document.hidden;
    };
    document.addEventListener('visibilitychange', onVisibility);
    return () => {
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, []);

  useEffect(() => {
    const unsubscribe = subscribeSystemMetrics((payload) => {
      const live = toLive(payload);
      setCurrent(live);
      setIsLive(true);

      if (hiddenRef.current) return;

      setHistory((prev) => {
        const next: MetricHistories = {
          cpu: pushHistory(prev.cpu, live.cpu, METRIC_HISTORY_LENGTH),
          ram: pushHistory(prev.ram, live.ram, METRIC_HISTORY_LENGTH),
          gpu: pushHistory(prev.gpu, live.gpu, METRIC_HISTORY_LENGTH),
          cpuTemp: pushHistory(prev.cpuTemp, live.cpuTemp, METRIC_HISTORY_LENGTH),
          netUp: pushHistory(prev.netUp, live.netUp, METRIC_HISTORY_LENGTH),
          netDown: pushHistory(prev.netDown, live.netDown, METRIC_HISTORY_LENGTH),
          disk: pushHistory(prev.disk, live.disk, METRIC_HISTORY_LENGTH),
        };
        return next;
      });
    });

    return () => {
      unsubscribe();
    };
  }, []);

  return { current, history, isLive };
}

// Re-export the list of metric keys for consumers that need to iterate
// over them (e.g. SystemPanel tiles in fixed order).
export { METRIC_KEYS };
