/**
 * Singleton WebSocket client for the JARVIS backend.
 *
 * Provides a stable, typed pub/sub surface so any module can subscribe to
 * message types without creating its own WebSocket connection. Reconnects
 * with exponential backoff (up to 30 s). Binary sends are passed through
 * directly (used for PCM mic frames from useMicStream).
 *
 * NOTE: Do not instantiate WebSocket anywhere else in the app. Import
 * and use `wsClient` instead.
 */

export type WsReadyState = 'connecting' | 'open' | 'closed';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type WsMessageHandler<T = unknown> = (payload: T) => void;

export interface WsClient {
    connect(url: string): void;
    disconnect(): void;
    /** Serialize `message` as JSON and send. Queues the send while connecting. */
    send(message: object): void;
    /** Send a raw binary frame (e.g. PCM Int16 from the mic). */
    sendBinary(data: ArrayBuffer): void;
    /**
     * Subscribe to incoming messages of the given `type` field.
     * Returns an unsubscribe function — call it on cleanup.
     */
    subscribe<T>(type: string, handler: WsMessageHandler<T>): () => void;
    /** Subscribe to connection-state changes. Returns unsubscribe. */
    onStateChange(handler: (state: WsReadyState) => void): () => void;
    getState(): WsReadyState;
}

// ---------------------------------------------------------------------------
// Internal implementation
// ---------------------------------------------------------------------------

const RECONNECT_INITIAL_MS = 1_000;
const RECONNECT_MAX_MS = 30_000;

interface ParsedMessage {
    type: string;
    [key: string]: unknown;
}

class WsClientImpl implements WsClient {
    private ws: WebSocket | null = null;
    private url: string | null = null;
    private state: WsReadyState = 'closed';

    /** Pending sends queued while connecting. */
    private sendQueue: Array<string | ArrayBuffer> = [];

    private reconnectDelay = RECONNECT_INITIAL_MS;
    private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    private destroyed = false;

    // Subscriber registries keyed by message type.
    private readonly subscribers = new Map<string, Set<WsMessageHandler>>();
    private readonly stateHandlers = new Set<(state: WsReadyState) => void>();

    // ---------------------------------------------------------------------------
    // Public API
    // ---------------------------------------------------------------------------

    connect(url: string): void {
        // Idempotent: if already connecting/open to the same URL, no-op.
        // This makes the call safe under React 18 StrictMode, where the
        // WebSocketProvider's effect runs mount → unmount → remount in dev,
        // and the provider may also re-render under HMR.
        if (this.url === url && this.ws !== null && this.state !== 'closed') {
            return;
        }
        // Switching URLs (rare): tear down first.
        if (this.ws !== null) {
            this.tearDown();
        }
        this.url = url;
        this.destroyed = false;
        this.openSocket();
    }

    disconnect(): void {
        this.destroyed = true;
        this.tearDown();
    }

    private tearDown(): void {
        if (this.reconnectTimer !== null) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
        if (this.ws !== null) {
            this.ws.onclose = null;
            try {
                this.ws.close();
            } catch {
                // ignore — close on a CONNECTING socket is best-effort
            }
            this.ws = null;
        }
        this.setReadyState('closed');
    }

    send(message: object): void {
        const serialized = JSON.stringify(message);
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(serialized);
        } else {
            this.sendQueue.push(serialized);
        }
    }

    sendBinary(data: ArrayBuffer): void {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(data);
        }
        // Binary frames are not queued — PCM audio is real-time-sensitive.
    }

    subscribe<T>(type: string, handler: WsMessageHandler<T>): () => void {
        if (!this.subscribers.has(type)) {
            this.subscribers.set(type, new Set());
        }
        const handlers = this.subscribers.get(type);
        // Cast: the Map stores WsMessageHandler<unknown> but the caller types T.
        const castHandler = handler as WsMessageHandler<unknown>;
        handlers?.add(castHandler);
        return () => {
            handlers?.delete(castHandler);
        };
    }

    onStateChange(handler: (state: WsReadyState) => void): () => void {
        this.stateHandlers.add(handler);
        return () => {
            this.stateHandlers.delete(handler);
        };
    }

    getState(): WsReadyState {
        return this.state;
    }

    // ---------------------------------------------------------------------------
    // Internal helpers
    // ---------------------------------------------------------------------------

    private openSocket(): void {
        if (!this.url) return;
        if (this.ws && this.ws.readyState <= WebSocket.OPEN) return;

        this.setReadyState('connecting');
        const ws = new WebSocket(this.url);
        this.ws = ws;

        ws.onopen = () => {
            if (this.ws !== ws) return; // Stale socket (reconnect race).
            this.reconnectDelay = RECONNECT_INITIAL_MS;
            this.setReadyState('open');
            this.flushQueue();
        };

        ws.onclose = () => {
            if (this.destroyed) return;
            this.ws = null;
            this.setReadyState('closed');
            this.scheduleReconnect();
        };

        ws.onerror = () => {
            ws.close();
        };

        ws.onmessage = (event: MessageEvent) => {
            if (typeof event.data !== 'string') return;
            try {
                const msg = JSON.parse(event.data) as ParsedMessage;
                const handlers = this.subscribers.get(msg.type);
                if (handlers) {
                    handlers.forEach((h) => {
                        try {
                            h(msg);
                        } catch (err) {
                            console.error(`[wsClient] handler for "${msg.type}" threw:`, err);
                        }
                    });
                }
            } catch (err) {
                console.error('[wsClient] JSON parse error:', err);
            }
        };
    }

    private flushQueue(): void {
        while (this.sendQueue.length > 0 && this.ws?.readyState === WebSocket.OPEN) {
            const item = this.sendQueue.shift();
            if (item !== undefined) {
                this.ws.send(item);
            }
        }
    }

    private scheduleReconnect(): void {
        if (this.destroyed) return;
        const delay = this.reconnectDelay;
        this.reconnectDelay = Math.min(delay * 2, RECONNECT_MAX_MS);
        this.reconnectTimer = setTimeout(() => {
            this.reconnectTimer = null;
            this.openSocket();
        }, delay);
    }

    private setReadyState(next: WsReadyState): void {
        if (this.state === next) return;
        this.state = next;
        this.stateHandlers.forEach((h) => {
            try {
                h(next);
            } catch (err) {
                console.error('[wsClient] stateChange handler threw:', err);
            }
        });
    }
}

// ---------------------------------------------------------------------------
// Module-level singleton
// ---------------------------------------------------------------------------

export const wsClient: WsClient = new WsClientImpl();
