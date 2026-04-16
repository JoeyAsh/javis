import { useEffect, useState } from 'react';

/**
 * Simple ticker that increments a counter every `intervalMs` unless paused.
 * Panels can derive animated mock values from the tick counter.
 */
export function useMockTicker(intervalMs: number = 2000, paused: boolean = false): number {
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (paused) return;
    const handle = window.setInterval(() => {
      setTick((t) => (t + 1) % 1_000_000);
    }, intervalMs);
    return () => {
      window.clearInterval(handle);
    };
  }, [intervalMs, paused]);

  return tick;
}

/**
 * Deterministic pseudo-random in [0,1) from integer seed — used to
 * reshuffle mock values across ticks without hooks needing refs.
 */
export function seededRand(seed: number): number {
  const x = Math.sin(seed * 9301 + 49297) * 233280;
  return x - Math.floor(x);
}
