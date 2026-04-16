import { useEffect, useRef, useState } from 'react';
import { subscribeTranscriptStream } from './useWebSocket';
import type { TranscriptTurn } from '../types';

/** Maximum transcript turns kept in memory — rolling window. */
const MAX_TURNS = 50;

export interface UseTranscriptsReturn {
  /** Ordered oldest → newest. */
  turns: TranscriptTurn[];
  /** True once at least one live turn has arrived. */
  isLive: boolean;
}

/**
 * Subscribes to the backend `transcript` WS stream and maintains a rolling
 * buffer of {@link TranscriptTurn}s. Consumers fall back to mock data when
 * `isLive === false`.
 */
export function useTranscripts(): UseTranscriptsReturn {
  const [turns, setTurns] = useState<TranscriptTurn[]>([]);
  const [isLive, setIsLive] = useState(false);
  const counterRef = useRef(0);

  useEffect(() => {
    const unsubscribe = subscribeTranscriptStream((payload) => {
      setIsLive(true);
      setTurns((prev) => {
        const next: TranscriptTurn = {
          id: `live-${Date.now()}-${counterRef.current++}`,
          role: payload.role,
          text: payload.text,
          at: new Date().toISOString(),
        };
        const combined = [...prev, next];
        return combined.length > MAX_TURNS
          ? combined.slice(combined.length - MAX_TURNS)
          : combined;
      });
    });
    return unsubscribe;
  }, []);

  return { turns, isLive };
}

export default useTranscripts;
