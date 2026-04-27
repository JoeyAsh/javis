/**
 * Tests for the API-token injection in wsClient.ts.
 *
 * Strategy:
 *  - Mock @core/api/tokenStore so getApiToken() is controllable.
 *  - Replace globalThis.WebSocket with a spy that records constructor call URLs.
 *  - Use vi.resetModules() + dynamic import to get a fresh wsClient singleton
 *    per test (required because wsClient is a module-level singleton).
 *
 * AC 15: wsClient.connect(url) appends ?token=<value> when token is non-empty;
 *         passes URL unchanged when token is "".
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// ---------------------------------------------------------------------------
// Mock tokenStore — set up before any dynamic imports.
// ---------------------------------------------------------------------------

vi.mock('@core/api/tokenStore', () => ({
    getApiToken: vi.fn(() => ''),
}));

import { getApiToken } from '@core/api/tokenStore';

const VALID_TOKEN = 'c'.repeat(64);
const BASE_URL = 'ws://localhost:8765/ws';
const BASE_URL_WITH_QUERY = 'ws://localhost:8765/ws?foo=bar';

// ---------------------------------------------------------------------------
// WebSocket constructor spy — tracks every URL passed to `new WebSocket(url)`.
// ---------------------------------------------------------------------------

let constructedUrls: string[] = [];

class SpyWebSocket {
    static readonly CONNECTING = 0;
    static readonly OPEN = 1;
    static readonly CLOSED = 3;

    readyState = SpyWebSocket.CONNECTING;
    onopen: ((ev: Event) => void) | null = null;
    onclose: ((ev: CloseEvent) => void) | null = null;
    onerror: ((ev: Event) => void) | null = null;
    onmessage: ((ev: MessageEvent) => void) | null = null;

    constructor(url: string) {
        constructedUrls.push(url);
    }

    close(): void {
        this.readyState = SpyWebSocket.CLOSED;
        this.onclose?.(new CloseEvent('close'));
    }

    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    send(_data: string | ArrayBuffer): void {}
}

beforeEach(() => {
    constructedUrls = [];
    vi.stubGlobal('WebSocket', SpyWebSocket);
    vi.useFakeTimers();
    vi.resetModules();
    // Reset getApiToken to return empty string by default.
    (getApiToken as ReturnType<typeof vi.fn>).mockReturnValue('');
});

afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.clearAllMocks();
    vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Helper: import a fresh wsClient after mocks are configured.
// ---------------------------------------------------------------------------

async function freshWsClient() {
    const mod = await import('../wsClient');
    return mod.wsClient;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('wsClient token injection — no token', () => {
    it('passes the bare URL unchanged to new WebSocket() when getApiToken returns ""', async () => {
        /**
         * AC 15: URL is not modified when token is empty.
         */
        (getApiToken as ReturnType<typeof vi.fn>).mockReturnValue('');
        const client = await freshWsClient();
        client.connect(BASE_URL);
        expect(constructedUrls).toHaveLength(1);
        expect(constructedUrls[0]).toBe(BASE_URL);
    });
});

describe('wsClient token injection — with token', () => {
    it('appends ?token=<value> to the URL when getApiToken returns a non-empty string', async () => {
        /**
         * AC 15: ?token=<value> appended when token is configured.
         */
        (getApiToken as ReturnType<typeof vi.fn>).mockReturnValue(VALID_TOKEN);
        const client = await freshWsClient();
        client.connect(BASE_URL);
        expect(constructedUrls).toHaveLength(1);
        expect(constructedUrls[0]).toContain(`token=${VALID_TOKEN}`);
    });

    it('appends &token=<value> when the base URL already has a query string', async () => {
        /**
         * Uses URL.searchParams.set — correctly handles pre-existing query params
         * by using & separator instead of ?.
         */
        (getApiToken as ReturnType<typeof vi.fn>).mockReturnValue(VALID_TOKEN);
        const client = await freshWsClient();
        client.connect(BASE_URL_WITH_QUERY);
        expect(constructedUrls).toHaveLength(1);
        const constructed = constructedUrls[0];
        // Both the original param and the token must be present.
        expect(constructed).toContain('foo=bar');
        expect(constructed).toContain(`token=${VALID_TOKEN}`);
        // The URL must NOT have a duplicate '?' (only one query separator).
        const questionMarkCount = (constructed.match(/\?/g) || []).length;
        expect(questionMarkCount).toBe(1);
    });
});

describe('wsClient token injection — idempotency (bare URL anchor)', () => {
    it('does not create a second WebSocket when connect() is called twice with the same bare URL', async () => {
        /**
         * The internal this.url stores the bare URL (without token) so that a second
         * call to connect(url) with the same bare URL is recognized as a no-op.
         * The WebSocket constructor must be invoked exactly once.
         */
        (getApiToken as ReturnType<typeof vi.fn>).mockReturnValue(VALID_TOKEN);
        const client = await freshWsClient();
        client.connect(BASE_URL);
        client.connect(BASE_URL); // second call — must be idempotent
        expect(constructedUrls).toHaveLength(1);
    });
});
