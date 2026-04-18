/**
 * useTurnTimings — subscribes to backend ``turn_timing`` WS messages and
 * maintains a ring buffer of the last 5 turns for the waterfall diagram.
 */
import { useEffect, useState } from 'react';
import type { TurnTimingPayload } from '../types';
import { subscribeTurnTimingStream } from './useWebSocket';

export interface UseTurnTimingsReturn {
  /** Last 5 turn-timing records, oldest first. */
  turns: ReadonlyArray<TurnTimingPayload>;
}

const MAX_TURNS = 5;

/**
 * Subscribe to per-turn latency waterfall events.
 *
 * @returns The last 5 `TurnTimingPayload` records (oldest first).
 */
export function useTurnTimings(): UseTurnTimingsReturn {
  const [turns, setTurns] = useState<ReadonlyArray<TurnTimingPayload>>([]);

  useEffect(() => {
    const unsub = subscribeTurnTimingStream((payload: TurnTimingPayload) => {
      setTurns((prev) => {
        const next = [...prev, payload];
        return next.length > MAX_TURNS ? next.slice(next.length - MAX_TURNS) : next;
      });
    });
    return unsub;
  }, []);

  return { turns };
}

export default useTurnTimings;
