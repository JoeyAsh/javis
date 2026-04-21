import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type React from 'react';
import type {
    AppOrbState,
    CalendarOpDonePayload,
    CalendarOpPreviewPayload,
    CalendarStatePayload,
    ConversationModePayload,
    EmailDraftPreviewPayload,
    EmailSendDonePayload,
    GitHubStatePayload,
    GitLabStatePayload,
    LogLinePayload,
    MailStatePayload,
    NotificationPayload,
    OrbState,
    SpotifyCmdAction,
    SpotifyStatePayload,
    SystemMetricsPayload,
    TranscriptPayload,
    TurnTimingPayload,
    WsIncoming,
    WsOutgoing,
} from '../types';

export type SystemMetricsListener = (payload: SystemMetricsPayload) => void;
export type TranscriptListener = (payload: TranscriptPayload) => void;
export type NotificationListener = (payload: NotificationPayload) => void;
export type ConversationModeListener = (payload: ConversationModePayload) => void;
export type MailStateListener = (payload: MailStatePayload) => void;
export type EmailDraftPreviewListener = (payload: EmailDraftPreviewPayload) => void;
export type EmailSendDoneListener = (payload: EmailSendDonePayload) => void;
export type SpotifyStateListener = (payload: SpotifyStatePayload) => void;
export type GitHubStateListener = (payload: GitHubStatePayload) => void;
export type CalendarStateListener = (payload: CalendarStatePayload) => void;
export type CalendarOpPreviewListener = (payload: CalendarOpPreviewPayload) => void;
export type CalendarOpDoneListener = (payload: CalendarOpDonePayload) => void;
export type GitLabStateListener = (payload: GitLabStatePayload) => void;
export type LogLineListener = (payload: LogLinePayload) => void;
export type TurnTimingListener = (payload: TurnTimingPayload) => void;

export interface UseWebSocketReturn {
    orbState: AppOrbState;
    setOrbState: (state: OrbState) => void;
    audioQueue: Array<{
        data: string;
        volume: number;
        channel: 'speech' | 'notification' | 'backchannel';
    }>;
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
    /** Subscribe to `type: 'mail_state'` payloads. */
    subscribeMailState: (listener: MailStateListener) => () => void;
    /** Subscribe to `type: 'email_draft_preview'` payloads. */
    subscribeEmailDraftPreview: (listener: EmailDraftPreviewListener) => () => void;
    /** Subscribe to `type: 'email_send_done'` payloads. */
    subscribeEmailSendDone: (listener: EmailSendDoneListener) => () => void;
    /** Subscribe to `type: 'spotify_state'` payloads. */
    subscribeSpotifyState: (listener: SpotifyStateListener) => () => void;
    /** Subscribe to `type: 'github_state'` payloads. */
    subscribeGitHubState: (listener: GitHubStateListener) => () => void;
    /** Subscribe to `type: 'calendar_state'` payloads. */
    subscribeCalendarState: (listener: CalendarStateListener) => () => void;
    /** Subscribe to `type: 'calendar_op_preview'` payloads. */
    subscribeCalendarOpPreview: (listener: CalendarOpPreviewListener) => () => void;
    /** Subscribe to `type: 'calendar_op_done'` payloads. */
    subscribeCalendarOpDone: (listener: CalendarOpDoneListener) => () => void;
    /** Subscribe to `type: 'gitlab_state'` payloads. */
    subscribeGitlabState: (listener: GitLabStateListener) => () => void;
    /** Subscribe to `type: 'log_line'` payloads (backend log stream). */
    subscribeLogLine: (listener: LogLineListener) => () => void;
    /** Subscribe to `type: 'turn_timing'` payloads (per-turn waterfall). */
    subscribeTurnTiming: (listener: TurnTimingListener) => () => void;
    /**
     * Send a Spotify command to the backend.
     * Phase 1: backend logs receipt; actual control is via voice → OpenClaw.
     * No-ops when WebSocket is not open.
     */
    sendSpotifyCmd: (action: SpotifyCmdAction, value?: number) => void;
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
const mailStateListeners = new Set<MailStateListener>();
const emailDraftPreviewListeners = new Set<EmailDraftPreviewListener>();
const emailSendDoneListeners = new Set<EmailSendDoneListener>();
const spotifyStateListeners = new Set<SpotifyStateListener>();
const gitHubStateListeners = new Set<GitHubStateListener>();
const calendarStateListeners = new Set<CalendarStateListener>();
const calendarOpPreviewListeners = new Set<CalendarOpPreviewListener>();
const calendarOpDoneListeners = new Set<CalendarOpDoneListener>();
const gitLabStateListeners = new Set<GitLabStateListener>();
const logLineListeners = new Set<LogLineListener>();
const turnTimingListeners = new Set<TurnTimingListener>();

// Module-level WS send reference — set by the hook on each connection so
// standalone send helpers (e.g. in panels that don't call useWebSocket()) can
// dispatch messages without prop-drilling.
let _moduleSend: ((data: string) => void) | null = null;

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

function emitMailState(payload: MailStatePayload): void {
    mailStateListeners.forEach((listener) => {
        try {
            listener(payload);
        } catch (err) {
            console.error('[ws] mail_state listener threw', err);
        }
    });
}

function emitEmailDraftPreview(payload: EmailDraftPreviewPayload): void {
    emailDraftPreviewListeners.forEach((listener) => {
        try {
            listener(payload);
        } catch (err) {
            console.error('[ws] email_draft_preview listener threw', err);
        }
    });
}

function emitEmailSendDone(payload: EmailSendDonePayload): void {
    emailSendDoneListeners.forEach((listener) => {
        try {
            listener(payload);
        } catch (err) {
            console.error('[ws] email_send_done listener threw', err);
        }
    });
}

function emitSpotifyState(payload: SpotifyStatePayload): void {
    spotifyStateListeners.forEach((listener) => {
        try {
            listener(payload);
        } catch (err) {
            console.error('[ws] spotify_state listener threw', err);
        }
    });
}

function emitGitHubState(payload: GitHubStatePayload): void {
    gitHubStateListeners.forEach((listener) => {
        try {
            listener(payload);
        } catch (err) {
            console.error('[ws] github_state listener threw', err);
        }
    });
}

function emitCalendarState(payload: CalendarStatePayload): void {
    calendarStateListeners.forEach((listener) => {
        try {
            listener(payload);
        } catch (err) {
            console.error('[ws] calendar_state listener threw', err);
        }
    });
}

function emitCalendarOpPreview(payload: CalendarOpPreviewPayload): void {
    calendarOpPreviewListeners.forEach((listener) => {
        try {
            listener(payload);
        } catch (err) {
            console.error('[ws] calendar_op_preview listener threw', err);
        }
    });
}

function emitCalendarOpDone(payload: CalendarOpDonePayload): void {
    calendarOpDoneListeners.forEach((listener) => {
        try {
            listener(payload);
        } catch (err) {
            console.error('[ws] calendar_op_done listener threw', err);
        }
    });
}

function emitGitLabState(payload: GitLabStatePayload): void {
    gitLabStateListeners.forEach((listener) => {
        try {
            listener(payload);
        } catch (err) {
            console.error('[ws] gitlab_state listener threw', err);
        }
    });
}

function emitLogLine(payload: LogLinePayload): void {
    logLineListeners.forEach((listener) => {
        try {
            listener(payload);
        } catch (err) {
            console.error('[ws] log_line listener threw', err);
        }
    });
}

function emitTurnTiming(payload: TurnTimingPayload): void {
    turnTimingListeners.forEach((listener) => {
        try {
            listener(payload);
        } catch (err) {
            console.error('[ws] turn_timing listener threw', err);
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
    const [audioQueue, setAudioQueue] = useState<
        Array<{ data: string; volume: number; channel: 'speech' | 'notification' | 'backchannel' }>
    >([]);
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
        if (
            pendingIdleRef.current &&
            audioQueue.length === 0 &&
            !isAudioPlaying &&
            toolCallCounter === 0
        ) {
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
            _moduleSend = (data: string) => ws.send(data);
        };

        ws.onclose = () => {
            setConnected(false);
            wsRef.current = null;
            _moduleSend = null;
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
                            const ch: 'speech' | 'notification' | 'backchannel' =
                                msg.channel === 'backchannel'
                                    ? 'backchannel'
                                    : msg.channel === 'notification'
                                      ? 'notification'
                                      : 'speech';
                            setAudioQueue((prev) => [
                                ...prev,
                                { data: msg.data, volume: vol, channel: ch },
                            ]);
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
                    case 'mail_state':
                        emitMailState(msg.payload);
                        break;
                    case 'email_draft_preview':
                        emitEmailDraftPreview(msg.payload);
                        break;
                    case 'email_send_done':
                        emitEmailSendDone(msg.payload);
                        break;
                    case 'spotify_state':
                        emitSpotifyState(msg.payload);
                        break;
                    case 'github_state':
                        emitGitHubState(msg.payload);
                        break;
                    case 'calendar_state':
                        emitCalendarState(msg.payload);
                        break;
                    case 'calendar_op_preview':
                        emitCalendarOpPreview(msg.payload);
                        break;
                    case 'calendar_op_done':
                        emitCalendarOpDone(msg.payload);
                        break;
                    case 'gitlab_state':
                        emitGitLabState(msg.payload);
                        break;
                    case 'log_line':
                        emitLogLine(msg.payload);
                        break;
                    case 'turn_timing':
                        emitTurnTiming(msg.payload);
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

    const subscribeSystem = useCallback((listener: SystemMetricsListener): (() => void) => {
        systemListeners.add(listener);
        return () => {
            systemListeners.delete(listener);
        };
    }, []);

    const subscribeTranscripts = useCallback((listener: TranscriptListener): (() => void) => {
        transcriptListeners.add(listener);
        return () => {
            transcriptListeners.delete(listener);
        };
    }, []);

    const subscribeNotifications = useCallback((listener: NotificationListener): (() => void) => {
        notificationListeners.add(listener);
        return () => {
            notificationListeners.delete(listener);
        };
    }, []);

    const subscribeConversationMode = useCallback(
        (listener: ConversationModeListener): (() => void) => {
            conversationModeListeners.add(listener);
            return () => {
                conversationModeListeners.delete(listener);
            };
        },
        [],
    );

    const subscribeMailState = useCallback((listener: MailStateListener): (() => void) => {
        mailStateListeners.add(listener);
        return () => {
            mailStateListeners.delete(listener);
        };
    }, []);

    const subscribeEmailDraftPreview = useCallback(
        (listener: EmailDraftPreviewListener): (() => void) => {
            emailDraftPreviewListeners.add(listener);
            return () => {
                emailDraftPreviewListeners.delete(listener);
            };
        },
        [],
    );

    const subscribeEmailSendDone = useCallback((listener: EmailSendDoneListener): (() => void) => {
        emailSendDoneListeners.add(listener);
        return () => {
            emailSendDoneListeners.delete(listener);
        };
    }, []);

    const subscribeSpotifyState = useCallback((listener: SpotifyStateListener): (() => void) => {
        spotifyStateListeners.add(listener);
        return () => {
            spotifyStateListeners.delete(listener);
        };
    }, []);

    const subscribeGitHubState = useCallback((listener: GitHubStateListener): (() => void) => {
        gitHubStateListeners.add(listener);
        return () => {
            gitHubStateListeners.delete(listener);
        };
    }, []);

    const subscribeCalendarState = useCallback((listener: CalendarStateListener): (() => void) => {
        calendarStateListeners.add(listener);
        return () => {
            calendarStateListeners.delete(listener);
        };
    }, []);

    const subscribeCalendarOpPreview = useCallback(
        (listener: CalendarOpPreviewListener): (() => void) => {
            calendarOpPreviewListeners.add(listener);
            return () => {
                calendarOpPreviewListeners.delete(listener);
            };
        },
        [],
    );

    const subscribeCalendarOpDone = useCallback(
        (listener: CalendarOpDoneListener): (() => void) => {
            calendarOpDoneListeners.add(listener);
            return () => {
                calendarOpDoneListeners.delete(listener);
            };
        },
        [],
    );

    const subscribeGitlabState = useCallback((listener: GitLabStateListener): (() => void) => {
        gitLabStateListeners.add(listener);
        return () => {
            gitLabStateListeners.delete(listener);
        };
    }, []);

    const subscribeLogLine = useCallback((listener: LogLineListener): (() => void) => {
        logLineListeners.add(listener);
        return () => {
            logLineListeners.delete(listener);
        };
    }, []);

    const subscribeTurnTiming = useCallback((listener: TurnTimingListener): (() => void) => {
        turnTimingListeners.add(listener);
        return () => {
            turnTimingListeners.delete(listener);
        };
    }, []);

    const sendSpotifyCmd = useCallback((action: SpotifyCmdAction, value?: number) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            const msg: WsOutgoing = {
                type: 'spotify_cmd',
                payload: value !== undefined ? { action, value } : { action },
            };
            wsRef.current.send(JSON.stringify(msg));
        }
    }, []);

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
        subscribeMailState,
        subscribeEmailDraftPreview,
        subscribeEmailSendDone,
        subscribeSpotifyState,
        subscribeGitHubState,
        subscribeCalendarState,
        subscribeCalendarOpPreview,
        subscribeCalendarOpDone,
        subscribeGitlabState,
        subscribeLogLine,
        subscribeTurnTiming,
        sendSpotifyCmd,
        registerStopAudio,
        notifyAudioPlaying,
        currentToolSummary,
    };
}

/**
 * Standalone subscription helpers — backed by the same module-level
 * registries so hook-instantiation order does not matter.
 */
export function subscribeSystemMetrics(listener: SystemMetricsListener): () => void {
    systemListeners.add(listener);
    return () => {
        systemListeners.delete(listener);
    };
}

export function subscribeTranscriptStream(listener: TranscriptListener): () => void {
    transcriptListeners.add(listener);
    return () => {
        transcriptListeners.delete(listener);
    };
}

export function subscribeNotificationStream(listener: NotificationListener): () => void {
    notificationListeners.add(listener);
    return () => {
        notificationListeners.delete(listener);
    };
}

export function subscribeConversationModeStream(listener: ConversationModeListener): () => void {
    conversationModeListeners.add(listener);
    return () => {
        conversationModeListeners.delete(listener);
    };
}

export function subscribeMailStateStream(listener: MailStateListener): () => void {
    mailStateListeners.add(listener);
    return () => {
        mailStateListeners.delete(listener);
    };
}

export function subscribeEmailDraftPreviewStream(listener: EmailDraftPreviewListener): () => void {
    emailDraftPreviewListeners.add(listener);
    return () => {
        emailDraftPreviewListeners.delete(listener);
    };
}

export function subscribeEmailSendDoneStream(listener: EmailSendDoneListener): () => void {
    emailSendDoneListeners.add(listener);
    return () => {
        emailSendDoneListeners.delete(listener);
    };
}

export function subscribeSpotifyStateStream(listener: SpotifyStateListener): () => void {
    spotifyStateListeners.add(listener);
    return () => {
        spotifyStateListeners.delete(listener);
    };
}

export function subscribeGitHubStateStream(listener: GitHubStateListener): () => void {
    /** Subscribe to `github_state` messages from the module-level registry. */
    gitHubStateListeners.add(listener);
    return () => {
        gitHubStateListeners.delete(listener);
    };
}

/** Subscribe to `calendar_state` messages from the module-level registry. */
export function subscribeCalendarStateStream(listener: CalendarStateListener): () => void {
    calendarStateListeners.add(listener);
    return () => {
        calendarStateListeners.delete(listener);
    };
}

/** Subscribe to `calendar_op_preview` messages from the module-level registry. */
export function subscribeCalendarOpPreviewStream(listener: CalendarOpPreviewListener): () => void {
    calendarOpPreviewListeners.add(listener);
    return () => {
        calendarOpPreviewListeners.delete(listener);
    };
}

/** Subscribe to `calendar_op_done` messages from the module-level registry. */
export function subscribeCalendarOpDoneStream(listener: CalendarOpDoneListener): () => void {
    calendarOpDoneListeners.add(listener);
    return () => {
        calendarOpDoneListeners.delete(listener);
    };
}

/**
 * Standalone Spotify command sender — backed by the same module-level WS
 * reference as the hook. No-ops when the WebSocket is not open. Usable from
 * panels that subscribe via `subscribeSpotifyStateStream` without calling
 * `useWebSocket()`.
 */
export function sendSpotifyCmdStream(action: SpotifyCmdAction, value?: number): void {
    if (!_moduleSend) return;
    const payload = value !== undefined ? { action, value } : { action };
    _moduleSend(JSON.stringify({ type: 'spotify_cmd', payload }));
}

/** Subscribe to `gitlab_state` messages from the module-level registry. */
export function subscribeGitLabStateStream(listener: GitLabStateListener): () => void {
    gitLabStateListeners.add(listener);
    return () => {
        gitLabStateListeners.delete(listener);
    };
}

/** Subscribe to `log_line` messages from the module-level registry. */
export function subscribeLogLineStream(listener: LogLineListener): () => void {
    logLineListeners.add(listener);
    return () => {
        logLineListeners.delete(listener);
    };
}

/** Subscribe to `turn_timing` messages from the module-level registry. */
export function subscribeTurnTimingStream(listener: TurnTimingListener): () => void {
    turnTimingListeners.add(listener);
    return () => {
        turnTimingListeners.delete(listener);
    };
}
