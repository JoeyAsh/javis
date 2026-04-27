// === FILE: frontend/src/features/brain/__tests__/brainApi.test.ts ===
/**
 * Tests for brainApi — RTK Query streamBrainInspector endpoint.
 *
 * Covers:
 *   - subscribe is called with 'brain_inspector' after cacheDataLoaded.
 *   - Incoming WS messages are dispatched as brainInspectorReceived actions.
 *   - unsubscribe is called exactly once when cacheEntryRemoved resolves
 *     (no subscription leak).
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { configureStore } from '@reduxjs/toolkit';
import { baseApi } from '@core/api/baseApi';

// ---------------------------------------------------------------------------
// Mock wsClient singleton — hoisted before any module import.
// ---------------------------------------------------------------------------

let mockSubscribeCallback: ((msg: unknown) => void) | null = null;
const mockUnsub = vi.fn();

vi.mock('@core/websocket/wsClient', () => ({
    wsClient: {
        subscribe: vi.fn((_type: string, cb: (msg: unknown) => void) => {
            mockSubscribeCallback = cb;
            return mockUnsub;
        }),
        send: vi.fn(),
        connect: vi.fn(),
        disconnect: vi.fn(),
        sendBinary: vi.fn(),
        onStateChange: vi.fn(() => vi.fn()),
        getState: vi.fn(() => 'closed'),
    },
}));

// ---------------------------------------------------------------------------
// Imports that depend on the mock being active.
// ---------------------------------------------------------------------------

import brainReducer from '../brainSlice';
import type { BrainState } from '../brainSlice';
import type { BrainInspectorPayload } from '../types';

// ---------------------------------------------------------------------------
// Store factory — fresh per test to avoid RTK Query cache hits.
// ---------------------------------------------------------------------------

function makeStore() {
    return configureStore({
        reducer: {
            [baseApi.reducerPath]: baseApi.reducer,
            brain: brainReducer,
        },
        middleware: (gdm) => gdm().concat(baseApi.middleware),
    });
}

// ---------------------------------------------------------------------------
// Flush pending microtasks so RTK Query's onCacheEntryAdded / cacheDataLoaded
// promise chain settles before assertions run.
// ---------------------------------------------------------------------------

async function flushMicrotasks(): Promise<void> {
    for (let i = 0; i < 10; i++) {
        await Promise.resolve();
    }
}

// ---------------------------------------------------------------------------
// Minimal valid BrainInspectorPayload for WS message simulation.
// ---------------------------------------------------------------------------

function makeBrainPayload(partial: Partial<BrainInspectorPayload> = {}): BrainInspectorPayload {
    return {
        voice_composer_status: {
            last_compose_ts: '2026-04-27T10:00:00.000Z',
            last_salutation: 'Sir',
        },
        ledger_recent: [],
        ledger_count_24h: { tts_emitted: 1, wake_word: 2 },
        ...partial,
    };
}

// ---------------------------------------------------------------------------
// Setup / Teardown
// ---------------------------------------------------------------------------

beforeEach(async () => {
    vi.useFakeTimers();
    mockSubscribeCallback = null;
    mockUnsub.mockReset();

    // Re-attach subscribe implementation each time vi.useFakeTimers() / restoreAllMocks
    // might have cleared it.
    const { wsClient } = await import('@core/websocket/wsClient');
    vi.mocked(wsClient.subscribe).mockImplementation(
        (_type: string, cb: (msg: unknown) => void) => {
            mockSubscribeCallback = cb;
            return mockUnsub;
        },
    );
});

afterEach(() => {
    vi.useRealTimers();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('streamBrainInspector', () => {
    it('subscribes to brain_inspector WS channel after cacheDataLoaded resolves', async () => {
        const store = makeStore();
        const { brainApi } = await import('../brainApi');
        const { wsClient } = await import('@core/websocket/wsClient');

        store.dispatch(brainApi.endpoints.streamBrainInspector.initiate());

        // Drain the RTK Query internal promise chain.
        await vi.advanceTimersByTimeAsync(0);
        await flushMicrotasks();

        expect(wsClient.subscribe).toHaveBeenCalledWith('brain_inspector', expect.any(Function));
        expect(mockSubscribeCallback).not.toBeNull();
    });

    it('dispatches brainInspectorReceived when a brain_inspector WS message arrives', async () => {
        const store = makeStore();
        const { brainApi } = await import('../brainApi');

        store.dispatch(brainApi.endpoints.streamBrainInspector.initiate());

        await vi.advanceTimersByTimeAsync(0);
        await flushMicrotasks();

        const incoming = makeBrainPayload({
            voice_composer_status: { last_compose_ts: '2026-04-27T11:00:00.000Z', last_salutation: 'Boss' },
            ledger_count_24h: { wake_word: 7 },
        });

        mockSubscribeCallback!({ type: 'brain_inspector', payload: incoming });

        const state = store.getState() as { brain: BrainState };
        expect(state.brain.voiceComposerStatus.last_salutation).toBe('Boss');
        expect(state.brain.counts24h.wake_word).toBe(7);
        expect(state.brain.lastInspectorTs).not.toBeNull();
    });

    it('calls unsubscribe exactly once when cacheEntryRemoved resolves (no subscription leak)', async () => {
        const store = makeStore();
        const { brainApi } = await import('../brainApi');

        const subscriptionResult = store.dispatch(
            brainApi.endpoints.streamBrainInspector.initiate(),
        );

        // Let cacheDataLoaded resolve so subscribe() is called.
        await vi.advanceTimersByTimeAsync(0);
        await flushMicrotasks();

        // Verify subscribe was called and unsub has NOT been called yet.
        const { wsClient } = await import('@core/websocket/wsClient');
        expect(wsClient.subscribe).toHaveBeenCalledWith('brain_inspector', expect.any(Function));
        expect(mockUnsub).not.toHaveBeenCalled();

        // Remove the only subscriber — RTK Query will remove the cache entry after
        // keepUnusedDataFor (default 60 s). Advance fake clock past that threshold.
        subscriptionResult.unsubscribe();
        await vi.advanceTimersByTimeAsync(61_000);
        await flushMicrotasks();

        // cacheEntryRemoved has resolved → unsubscribe() must be called exactly once.
        expect(mockUnsub).toHaveBeenCalledTimes(1);
    });
});
