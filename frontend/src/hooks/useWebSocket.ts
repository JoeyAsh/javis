import { useCallback, useEffect, useRef, useState } from 'react';
import type React from 'react';
import type { OrbState, WsIncoming, WsOutgoing } from '../types';

export interface UseWebSocketReturn {
  orbState: OrbState;
  setOrbState: (state: OrbState) => void;
  audioQueue: string[];
  consumeAudio: () => void;
  sendTranscript: (text: string) => void;
  connected: boolean;
  /** Raw WebSocket ref — exposed so useMicStream can send binary PCM frames */
  wsRef: React.RefObject<WebSocket | null>;
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
          // system metrics ignored for now
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

  return { orbState, setOrbState, audioQueue, consumeAudio, sendTranscript, connected, wsRef };
}
