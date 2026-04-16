import { useCallback, useEffect, useRef, useState } from 'react';
import type React from 'react';
import type {
  OrbState,
  SystemMetricsPayload,
  WsIncoming,
  WsOutgoing,
} from '../types';

export type SystemMetricsListener = (payload: SystemMetricsPayload) => void;

export interface UseWebSocketReturn {
  orbState: OrbState;
  setOrbState: (state: OrbState) => void;
  audioQueue: string[];
  consumeAudio: () => void;
  sendTranscript: (text: string) => void;
  connected: boolean;
  /** Raw WebSocket ref — exposed so useMicStream can send binary PCM frames */
  wsRef: React.RefObject<WebSocket | null>;
  /**
   * Subscribe to `type: 'system'` payloads. Returns an unsubscribe fn.
   * Used by {@link useSystemMetrics} to fan out live metrics without
   * tying their cadence to the React re-render cycle.
   */
  subscribeSystem: (listener: SystemMetricsListener) => () => void;
}

// Module-level subscriber registry so any consumer calling the singleton
// `useWebSocket` sees the same stream of system payloads.
const systemListeners = new Set<SystemMetricsListener>();

function emitSystem(payload: SystemMetricsPayload): void {
  systemListeners.forEach((listener) => {
    try {
      listener(payload);
    } catch (err) {
      console.error('[ws] system listener threw', err);
    }
  });
}

const RECONNECT_DELAY_INITIAL = 1000;
const RECONNECT_DELAY_MAX = 30000;

/**
 * Hook to manage WebSocket connection to JARVIS backend.
 * Receives: audio (base64 MP3), status, metrics, text fallback.
 * Sends: transcript messages from speech recognition.
 */
export function useWebSocket(): UseWebSocketReturn {
  const [orbState, setOrbState] = useState<OrbState>('idle');
  const [audioQueue, setAudioQueue] = useState<string[]>([]);
  const [connected, setConnected] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectDelayRef = useRef(RECONNECT_DELAY_INITIAL);

  const connect = useCallback(() => {
    // StrictMode guard: only one connection at a time
    if (wsRef.current && wsRef.current.readyState <= WebSocket.OPEN) {
      return;
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.hostname}:8765`;

    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      setConnected(true);
      reconnectDelayRef.current = RECONNECT_DELAY_INITIAL;
    };

    ws.onclose = () => {
      setConnected(false);
      wsRef.current = null;
      const delay = reconnectDelayRef.current;
      reconnectDelayRef.current = Math.min(delay * 2, RECONNECT_DELAY_MAX);
      reconnectTimeoutRef.current = setTimeout(() => {
        connect();
      }, delay);
    };

    ws.onerror = (err) => {
      console.error('[ws] error', err);
      ws.close();
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data as string) as WsIncoming;
        switch (msg.type) {
          case 'status':
            setOrbState(msg.state);
            break;
          case 'audio':
            if (msg.data) {
              setOrbState('speaking');
              setAudioQueue((prev) => [...prev, msg.data]);
            } else {
              // TTS failed — return to idle
              setOrbState('idle');
            }
            break;
          case 'text':
            // Text-only fallback when TTS fails — log and return to idle
            console.log('[JARVIS]', msg.text);
            setOrbState('idle');
            break;
          case 'system':
            emitSystem(msg.payload);
            break;
        }
      } catch (err) {
        console.error('[ws] parse error', err);
      }
    };

    wsRef.current = ws;
  }, []);

  useEffect(() => {
    connect();

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
      if (wsRef.current) {
        // Prevent reconnect on cleanup
        wsRef.current.onclose = null;
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect]);

  const consumeAudio = useCallback(() => {
    setAudioQueue((prev) => prev.slice(1));
  }, []);

  const sendTranscript = useCallback((text: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      const msg: WsOutgoing = { type: 'transcript', text, isFinal: true };
      wsRef.current.send(JSON.stringify(msg));
    }
  }, []);

  const subscribeSystem = useCallback(
    (listener: SystemMetricsListener): (() => void) => {
      systemListeners.add(listener);
      return () => {
        systemListeners.delete(listener);
      };
    },
    [],
  );

  return {
    orbState,
    setOrbState,
    audioQueue,
    consumeAudio,
    sendTranscript,
    connected,
    wsRef,
    subscribeSystem,
  };
}

/**
 * Standalone subscription helper for consumers that don't need the full
 * `useWebSocket` surface. Backed by the same module-level registry so
 * order of hook instantiation does not matter.
 */
export function subscribeSystemMetrics(
  listener: SystemMetricsListener,
): () => void {
  systemListeners.add(listener);
  return () => {
    systemListeners.delete(listener);
  };
}
