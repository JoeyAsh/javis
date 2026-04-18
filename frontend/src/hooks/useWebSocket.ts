import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type React from 'react';
import type {
  AppOrbState,
  ConversationModePayload,
  NotificationPayload,
  OrbState,
  SystemMetricsPayload,
  TranscriptPayload,
  WsIncoming,
  WsOutgoing,
} from '../types';

export type SystemMetricsListener = (payload: SystemMetricsPayload) => void;
export type TranscriptListener = (payload: TranscriptPayload) => void;
export type NotificationListener = (payload: NotificationPayload) => void;
export type ConversationModeListener = (payload: ConversationModePayload) => void;

export interface UseWebSocketReturn {
  orbState: AppOrbState;
  setOrbState: (state: OrbState) => void;
  audioQueue: Array<{ data: string; volume: number }>;
  consumeAudio: () => void;
  sendTranscript: (text: string) => void;
  /**
   * Emergency STOP — ask the backend to abort any in-flight voice turn
   * for this connection. Safe to call repeatedly; the backend replies
   * with ``status=idle`` + a ``Konversation gestoppt`` info notification.
   */
  sendCancelTurn: () => void;
  connected: boolean;
  /** Raw WebSocket ref — exposed so useMicStream can send binary PCM frames */
  wsRef: React.RefObject<WebSocket | null>;
  /**
   * Subscribe to `type: 'system'` payloads. Returns an unsubscribe fn.
   * Used by {@link useSystemMetrics} to fan out live metrics without
   * tying their cadence to the React re-render cycle.
   */
  subscribeSystem: (listener: SystemMetricsListener) => () => void;
  /** Subscribe to `type: 'transcript'` payloads. */
  subscribeTranscripts: (listener: TranscriptListener) => () => void;
  /** Subscribe to `type: 'notification'` payloads. */
  subscribeNotifications: (listener: NotificationListener) => () => void;
  /** Subscribe to `type: 'conversation_mode'` payloads. */
  subscribeConversationMode: (listener: ConversationModeListener) => () => void;
  /**
   * Callback registered by the audio player (useAudioAnalyser) so that a
   * ``barge_in`` message can immediately stop in-progress audio. Call
   * ``registerStopAudio`` once on mount; the hook stores the reference
   * and calls it when barge_in arrives.
   */
  registerStopAudio: (fn: () => void) => void;
  /**
   * Notify the hook that audio playback started or ended. Called by the audio
   * player (App.tsx / useAudioAnalyser) so the hook can keep the orb in
   * `speaking` until all queued clips have actually finished playing.
   */
  notifyAudioPlaying: (playing: boolean) => void;
  /**
   * Human-readable description of the tool call currently in flight, or
   * `null` when no tool calls are active. E.g. "Lese config/config.yaml".
   * Consumers may render this as a status chip near the orb.
   */
  currentToolSummary: string | null;
}

// Module-level subscriber registries — any consumer of the singleton
// useWebSocket sees the same stream of payloads.
const systemListeners = new Set<SystemMetricsListener>();
const transcriptListeners = new Set<TranscriptListener>();
const notificationListeners = new Set<NotificationListener>();
const conversationModeListeners = new Set<ConversationModeListener>();

function emitSystem(payload: SystemMetricsPayload): void {
  systemListeners.forEach((listener) => {
    try {
      listener(payload);
    } catch (err) {
      console.error('[ws] system listener threw', err);
    }
  });
}

function emitTranscript(payload: TranscriptPayload): void {
  transcriptListeners.forEach((listener) => {
    try {
      listener(payload);
    } catch (err) {
      console.error('[ws] transcript listener threw', err);
    }
  });
}

function emitNotification(payload: NotificationPayload): void {
  notificationListeners.forEach((listener) => {
    try {
      listener(payload);
    } catch (err) {
      console.error('[ws] notification listener threw', err);
    }
  });
}

function emitConversationMode(payload: ConversationModePayload): void {
  conversationModeListeners.forEach((listener) => {
    try {
      listener(payload);
    } catch (err) {
      console.error('[ws] conversation_mode listener threw', err);
    }
  });
}

const RECONNECT_DELAY_INITIAL = 1000;
const RECONNECT_DELAY_MAX = 30000;

/**
 * Hook to manage WebSocket connection to JARVIS backend.
 * Receives: audio (base64 MP3), status, metrics, text fallback.
 * Sends: transcript messages from speech recognition.
 *
 * ## Orb state priority chain
 * The displayed `orbState` is a derived value computed from three independent
 * signals. In descending priority:
 *   1. **working** — if `toolCallCounterRef.current > 0`, the orb is `working`
 *      regardless of audio or backend state. Resets when all in-flight tool
 *      calls finish.
 *   2. **speaking** — if `audioQueue.length > 0` OR `isAudioPlayingRef.current`
 *      is true, the orb stays `speaking` even if the backend has already sent
 *      `status=idle`. A `pendingIdleRef` flag captures the backend's idle intent
 *      and fires the transition only once all audio is consumed.
 *   3. **backend state** — whatever the last `status` frame from the backend
 *      dictated (stored in `backendStateRef`).
 *
 * This prevents the orb from visually dropping to idle while TTS audio is still
 * playing, and keeps it visually active while Claude Code tools are running.
 */
export function useWebSocket(): UseWebSocketReturn {
  const [audioQueue, setAudioQueue] = useState<Array<{ data: string; volume: number }>>([]);
  const [connected, setConnected] = useState(false);

  // --- Orb state derivation state ---
  // `backendState` is the last OrbState pushed by the backend's `status` frame.
  const [backendState, setBackendState] = useState<OrbState>('idle');
  // `toolCallCounter` counts in-flight tool_call events. When > 0, orb = working.
  const [toolCallCounter, setToolCallCounter] = useState(0);
  // `isAudioPlaying` mirrors whether the audio player currently has a clip playing.
  const [isAudioPlaying, setIsAudioPlaying] = useState(false);
  // `currentToolSummary` holds the summary of the most recent in-flight tool call.
  const [currentToolSummary, setCurrentToolSummary] = useState<string | null>(null);

  // Ref mirrors of the above for use inside `onmessage` closure (avoids stale captures).
  const toolCallCounterRef = useRef(0);
  const isAudioPlayingRef = useRef(false);
  const audioQueueLengthRef = useRef(0);
  // When the backend sends `status=idle` but audio is still playing/queued, we
  // park the idle intent here and fire it when audio drains.
  const pendingIdleRef = useRef(false);

  // --- Derived orb state (priority chain) ---
  const orbState: AppOrbState = useMemo(() => {
    if (toolCallCounter > 0) return 'working';
    if (audioQueue.length > 0 || isAudioPlaying) return 'speaking';
    return backendState;
  }, [toolCallCounter, audioQueue.length, isAudioPlaying, backendState]);

  // When audio drains completely and pendingIdleRef is set, flush to idle.
  useEffect(() => {
    if (pendingIdleRef.current && audioQueue.length === 0 && !isAudioPlaying && toolCallCounter === 0) {
      pendingIdleRef.current = false;
      setBackendState('idle');
    }
  }, [audioQueue.length, isAudioPlaying, toolCallCounter]);

  // Keep ref mirror of audioQueue length for onmessage closure.
  useEffect(() => {
    audioQueueLengthRef.current = audioQueue.length;
  }, [audioQueue.length]);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectDelayRef = useRef(RECONNECT_DELAY_INITIAL);
  const hasEverOpenedRef = useRef(false);
  const consecutiveErrorsRef = useRef(0);
  // Callback registered by the audio player so barge_in can stop it.
  const stopAudioRef = useRef<(() => void) | null>(null);

  // Threshold before escalating suppressed WS errors to console.warn.
  const ERROR_WARN_THRESHOLD = 3;

  const connect = useCallback(() => {
    // StrictMode guard: only one connection at a time
    if (wsRef.current && wsRef.current.readyState <= WebSocket.OPEN) {
      return;
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.hostname}:8765`;

    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      hasEverOpenedRef.current = true;
      consecutiveErrorsRef.current = 0;
      console.info('[ws] connected');
      setConnected(true);
      reconnectDelayRef.current = RECONNECT_DELAY_INITIAL;
    };

    ws.onclose = () => {
      setConnected(false);
      wsRef.current = null;
      const delay = reconnectDelayRef.current;
      reconnectDelayRef.current = Math.min(delay * 2, RECONNECT_DELAY_MAX);
      console.info(`[ws] disconnected, retrying in ${delay}ms`);
      reconnectTimeoutRef.current = setTimeout(() => {
        connect();
      }, delay);
    };

    ws.onerror = (err) => {
      const count = consecutiveErrorsRef.current + 1;
      consecutiveErrorsRef.current = count;

      if (!hasEverOpenedRef.current || count <= ERROR_WARN_THRESHOLD) {
        console.debug('[ws] error', err);
      } else if (count === ERROR_WARN_THRESHOLD + 1) {
        console.warn(`[ws] backend unreachable after ${count} attempts`);
      }
      ws.close();
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data as string) as WsIncoming;
        switch (msg.type) {
          case 'status': {
            const incomingState = msg.state;
            if (incomingState === 'idle') {
              // If audio is still playing/queued, defer the idle transition.
              if (audioQueueLengthRef.current > 0 || isAudioPlayingRef.current) {
                pendingIdleRef.current = true;
              } else {
                pendingIdleRef.current = false;
                setBackendState('idle');
              }
            } else {
              pendingIdleRef.current = false;
              setBackendState(incomingState);
            }
            break;
          }
          case 'audio':
            if (msg.data) {
              // Ensure backend state reflects speaking so the chain resolves correctly.
              setBackendState('speaking');
              pendingIdleRef.current = false;
              // Backchannel clips play at 30% volume; all other clips at full.
              const vol = msg.channel === 'backchannel' ? 0.3 : 1.0;
              setAudioQueue((prev) => [...prev, { data: msg.data, volume: vol }]);
            } else {
              // TTS failed — return to idle
              setBackendState('idle');
            }
            break;
          case 'barge_in':
            // Drop pending audio queue and stop the currently playing clip.
            pendingIdleRef.current = false;
            setAudioQueue([]);
            audioQueueLengthRef.current = 0;
            stopAudioRef.current?.();
            setIsAudioPlaying(false);
            isAudioPlayingRef.current = false;
            setBackendState('listening');
            break;
          case 'text':
            // Text-only fallback when TTS fails — log and return to idle
            console.log('[JARVIS]', msg.text);
            setBackendState('idle');
            break;
          case 'system':
            emitSystem(msg.payload);
            break;
          case 'transcript':
            emitTranscript(msg.payload);
            break;
          case 'notification':
            emitNotification(msg.payload);
            break;
          case 'conversation_mode':
            emitConversationMode(msg.payload);
            break;
          case 'tool_call': {
            const { state: tcState, summary } = msg.payload;
            if (tcState === 'started') {
              const newCount = toolCallCounterRef.current + 1;
              toolCallCounterRef.current = newCount;
              setToolCallCounter(newCount);
              if (summary) setCurrentToolSummary(summary);
            } else {
              // finished
              const newCount = Math.max(0, toolCallCounterRef.current - 1);
              toolCallCounterRef.current = newCount;
              setToolCallCounter(newCount);
              if (newCount === 0) setCurrentToolSummary(null);
            }
            break;
          }
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

  const notifyAudioPlaying = useCallback((playing: boolean) => {
    isAudioPlayingRef.current = playing;
    setIsAudioPlaying(playing);
  }, []);

  /**
   * Legacy setOrbState — kept for backward compatibility with the dev menu
   * override and barge_in paths. Sets the backend state directly.
   */
  const setOrbState = useCallback((state: OrbState) => {
    setBackendState(state);
  }, []);

  const registerStopAudio = useCallback((fn: () => void) => {
    stopAudioRef.current = fn;
  }, []);

  const sendTranscript = useCallback((text: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      const msg: WsOutgoing = { type: 'transcript', text, isFinal: true };
      wsRef.current.send(JSON.stringify(msg));
    }
  }, []);

  const sendCancelTurn = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      const msg: WsOutgoing = { type: 'cancel_turn' };
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

  const subscribeTranscripts = useCallback(
    (listener: TranscriptListener): (() => void) => {
      transcriptListeners.add(listener);
      return () => {
        transcriptListeners.delete(listener);
      };
    },
    [],
  );

  const subscribeNotifications = useCallback(
    (listener: NotificationListener): (() => void) => {
      notificationListeners.add(listener);
      return () => {
        notificationListeners.delete(listener);
      };
    },
    [],
  );

  const subscribeConversationMode = useCallback(
    (listener: ConversationModeListener): (() => void) => {
      conversationModeListeners.add(listener);
      return () => {
        conversationModeListeners.delete(listener);
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
    sendCancelTurn,
    connected,
    wsRef,
    subscribeSystem,
    subscribeTranscripts,
    subscribeNotifications,
    subscribeConversationMode,
    registerStopAudio,
    notifyAudioPlaying,
    currentToolSummary,
  };
}

/**
 * Standalone subscription helpers — backed by the same module-level
 * registries so hook-instantiation order does not matter.
 */
export function subscribeSystemMetrics(
  listener: SystemMetricsListener,
): () => void {
  systemListeners.add(listener);
  return () => {
    systemListeners.delete(listener);
  };
}

export function subscribeTranscriptStream(
  listener: TranscriptListener,
): () => void {
  transcriptListeners.add(listener);
  return () => {
    transcriptListeners.delete(listener);
  };
}

export function subscribeNotificationStream(
  listener: NotificationListener,
): () => void {
  notificationListeners.add(listener);
  return () => {
    notificationListeners.delete(listener);
  };
}

export function subscribeConversationModeStream(
  listener: ConversationModeListener,
): () => void {
  conversationModeListeners.add(listener);
  return () => {
    conversationModeListeners.delete(listener);
  };
}
