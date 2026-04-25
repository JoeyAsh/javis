/**
 * wsClient singleton — Vitest unit tests.
 *
 * Strategy: stub window.WebSocket with a lightweight mock so no real network
 * connection is opened. Tests cover the subscribe/unsubscribe routing contract,
 * the send queue behaviour while connecting, binary drop while closed, and the
 * onStateChange notification path.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// ---------------------------------------------------------------------------
// Mock WebSocket
// ---------------------------------------------------------------------------

interface MockWsInstance {
    onopen: ((ev: Event) => void) | null;
    onclose: ((ev: CloseEvent) => void) | null;
    onerror: ((ev: Event) => void) | null;
    onmessage: ((ev: MessageEvent) => void) | null;
    readyState: number;
    close(): void;
    send(data: string | ArrayBuffer): void;
}

let latestWs: MockWsInstance | null = null;
const sentFrames: Array<string | ArrayBuffer> = [];

class MockWebSocket implements MockWsInstance {
    static readonly CONNECTING = 0;
    static readonly OPEN = 1;
    static readonly CLOSED = 3;

    readyState = MockWebSocket.CONNECTING;
    onopen: ((ev: Event) => void) | null = null;
    onclose: ((ev: CloseEvent) => void) | null = null;
    onerror: ((ev: Event) => void) | null = null;
    onmessage: ((ev: MessageEvent) => void) | null = null;

    constructor(_url: string) {
        latestWs = this;
    }

    close(): void {
        this.readyState = MockWebSocket.CLOSED;
        this.onclose?.(new CloseEvent('close'));
    }

    send(data: string | ArrayBuffer): void {
        sentFrames.push(data);
    }
}

function openWs(): void {
    if (latestWs) {
        latestWs.readyState = MockWebSocket.OPEN;
        latestWs.onopen?.(new Event('open'));
    }
}

function injectMessage(data: unknown): void {
    latestWs?.onmessage?.(
        new MessageEvent('message', { data: JSON.stringify(data) }),
    );
}

// ---------------------------------------------------------------------------
// Re-import wsClient fresh for each test group via module reset
// ---------------------------------------------------------------------------

// We need a fresh wsClient for each test to reset internal state.
// Because wsClient is a module-level singleton, we use vi.resetModules()
// and dynamic re-import to get an isolated instance per test.

beforeEach(() => {
    latestWs = null;
    sentFrames.length = 0;
    vi.stubGlobal('WebSocket', MockWebSocket);
    vi.useFakeTimers();
    vi.resetModules();
});

afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('wsClient — subscribe routes by type', () => {
    it('dispatches an incoming message to the correct subscriber', async () => {
        const { wsClient } = await import('../wsClient');
        wsClient.connect('ws://localhost:8765');
        openWs();

        const received: unknown[] = [];
        wsClient.subscribe('test_type', (msg) => received.push(msg));

        injectMessage({ type: 'test_type', payload: { value: 42 } });

        expect(received).toHaveLength(1);
        expect((received[0] as { payload: { value: number } }).payload.value).toBe(42);
    });

    it('does NOT dispatch to a subscriber of a different type', async () => {
        const { wsClient } = await import('../wsClient');
        wsClient.connect('ws://localhost:8765');
        openWs();

        const received: unknown[] = [];
        wsClient.subscribe('other_type', (msg) => received.push(msg));

        injectMessage({ type: 'test_type', payload: 'should not arrive' });

        expect(received).toHaveLength(0);
    });
});

describe('wsClient — unsubscribe removes handler', () => {
    it('stops delivering messages after the returned unsub fn is called', async () => {
        const { wsClient } = await import('../wsClient');
        wsClient.connect('ws://localhost:8765');
        openWs();

        const received: unknown[] = [];
        const unsub = wsClient.subscribe('evt', (msg) => received.push(msg));

        // Fires once.
        injectMessage({ type: 'evt', payload: 'first' });
        expect(received).toHaveLength(1);

        // Unsubscribe — no further deliveries.
        unsub();
        injectMessage({ type: 'evt', payload: 'second' });
        expect(received).toHaveLength(1);
    });
});

describe('wsClient — send queues while connecting', () => {
    it('flushes queued messages once the socket opens', async () => {
        const { wsClient } = await import('../wsClient');
        wsClient.connect('ws://localhost:8765');
        // NOT open yet — still CONNECTING.

        wsClient.send({ type: 'hello' });
        wsClient.send({ type: 'world' });
        // Nothing sent yet.
        expect(sentFrames).toHaveLength(0);

        // Open the socket — queue should flush.
        openWs();

        expect(sentFrames).toHaveLength(2);
        const first = JSON.parse(sentFrames[0] as string) as { type: string };
        const second = JSON.parse(sentFrames[1] as string) as { type: string };
        expect(first.type).toBe('hello');
        expect(second.type).toBe('world');
    });
});

describe('wsClient — sendBinary drops while closed', () => {
    it('does not throw and sends nothing when WS is not open', async () => {
        const { wsClient } = await import('../wsClient');
        wsClient.connect('ws://localhost:8765');
        // Still CONNECTING — do NOT open.

        const buf = new ArrayBuffer(4);
        expect(() => wsClient.sendBinary(buf)).not.toThrow();
        expect(sentFrames).toHaveLength(0);
    });
});

describe('wsClient — onStateChange fires on open/close', () => {
    it('calls handler with "open" when socket connects', async () => {
        const { wsClient } = await import('../wsClient');
        wsClient.connect('ws://localhost:8765');

        const states: string[] = [];
        wsClient.onStateChange((s) => states.push(s));

        openWs();

        expect(states).toContain('open');
    });

    it('calls handler with "closed" when socket disconnects', async () => {
        const { wsClient } = await import('../wsClient');
        wsClient.connect('ws://localhost:8765');

        const states: string[] = [];
        wsClient.onStateChange((s) => states.push(s));

        openWs();
        latestWs?.close();

        expect(states).toContain('closed');
    });

    it('returned unsub stops state-change notifications', async () => {
        const { wsClient } = await import('../wsClient');
        wsClient.connect('ws://localhost:8765');

        const states: string[] = [];
        const unsub = wsClient.onStateChange((s) => states.push(s));

        unsub();
        openWs();

        expect(states).toHaveLength(0);
    });
});
