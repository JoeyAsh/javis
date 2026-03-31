import { useCallback, useEffect, useRef, useState } from 'react';
import type {
  OrbState,
  SystemStats,
  TranscriptEntry,
  WsCommand,
  WsMessage,
} from '../types';

interface UseWebSocketReturn {
  orbState: OrbState;
  transcript: TranscriptEntry[];
  systemStats: SystemStats | null;
  send: (cmd: WsCommand) => void;
  connected: boolean;
}

const MAX_TRANSCRIPT_ENTRIES = 6;
const RECONNECT_DELAY = 3000;

/**
 * Hook to manage WebSocket connection to JARVIS backend.
 */
export function useWebSocket(): UseWebSocketReturn {
  const [orbState, setOrbState] = useState<OrbState>('idle');
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([]);
  const [systemStats, setSystemStats] = useState<SystemStats | null>(null);
  const [connected, setConnected] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const transcriptIdRef = useRef(0);
  const reconnectTimeoutRef = useRef<number | null>(null);

  const connect = useCallback(() => {
    // Determine WebSocket URL
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;

    // Use /ws path for Vite proxy in development, direct port in production
    let wsUrl: string;
    if (import.meta.env.DEV) {
      wsUrl = `${protocol}//${host}/ws`;
    } else {
      // In production, connect directly to backend port
      wsUrl = `${protocol}//${window.location.hostname}:8765`;
    }

    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      setConnected(true);
      console.log('WebSocket connected');
    };

    ws.onclose = () => {
      setConnected(false);
      console.log('WebSocket disconnected, reconnecting...');

      // Auto-reconnect
      reconnectTimeoutRef.current = window.setTimeout(() => {
        connect();
      }, RECONNECT_DELAY);
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data) as WsMessage;

        switch (message.type) {
          case 'state':
            setOrbState(message.payload);
            break;

          case 'transcript':
            setTranscript((prev) => {
              const newEntry: TranscriptEntry = {
                ...message.payload,
                id: transcriptIdRef.current++,
              };
              const updated = [...prev, newEntry];
              // Keep only the last N entries
              return updated.slice(-MAX_TRANSCRIPT_ENTRIES);
            });
            break;

          case 'system':
            setSystemStats(message.payload);
            break;
        }
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error);
      }
    };

    wsRef.current = ws;
  }, []);

  useEffect(() => {
    connect();

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect]);

  const send = useCallback((cmd: WsCommand) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(cmd));
    }
  }, []);

  return {
    orbState,
    transcript,
    systemStats,
    send,
    connected,
  };
}
