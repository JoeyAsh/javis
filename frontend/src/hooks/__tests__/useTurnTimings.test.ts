/**
 * useTurnTimings — unit tests.
 *
 * Tests:
 * 1. Initial state: empty turns array.
 * 2. Subscribes to turn_timing stream on mount.
 * 3. Appends incoming turn records.
 * 4. Keeps only last 5 turns (ring buffer).
 * 5. Unsubscribes on unmount.
 */
import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// ---------------------------------------------------------------------------
// Mock subscribeTurnTimingStream
// ---------------------------------------------------------------------------

vi.mock('../useWebSocket', () => {
    let _stored: ((payload: import('../../types').TurnTimingPayload) => void) | null = null;

    return {
        subscribeTurnTimingStream: vi.fn((listener) => {
            _stored = listener;
            return () => {
                _stored = null;
            };
        }),
        __fireTurnTiming: (payload: import('../../types').TurnTimingPayload) => {
            if (_stored) _stored(payload);
        },
    };
});

import { subscribeTurnTimingStream } from '../useWebSocket';
import { useTurnTimings } from '../useTurnTimings';
import type { TurnTimingPayload } from '../../types';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const mod = (await import('../useWebSocket')) as any;
const fireTurnTiming = (payload: TurnTimingPayload) => mod.__fireTurnTiming(payload);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

let _counter = 0;
function makeTurn(overrides: Partial<TurnTimingPayload> = {}): TurnTimingPayload {
    _counter += 1;
    const base = Date.now();
    return {
        turn_id: `turn-${_counter}`,
        audio_end_ts: base,
        stt_done_ts: base + 300,
        llm_first_token_ts: base + 800,
        llm_done_ts: base + 2000,
        tts_first_audio_ts: base + 900,
        tts_done_ts: base + 2500,
        ...overrides,
    };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('useTurnTimings', () => {
    beforeEach(() => {
        vi.mocked(subscribeTurnTimingStream).mockClear();
        _counter = 0;
    });

    afterEach(() => {
        vi.restoreAllMocks();
    });

    it('starts with empty turns', () => {
        const { result } = renderHook(() => useTurnTimings());
        expect(result.current.turns).toHaveLength(0);
    });

    it('calls subscribeTurnTimingStream on mount', () => {
        renderHook(() => useTurnTimings());
        expect(subscribeTurnTimingStream).toHaveBeenCalledTimes(1);
    });

    it('appends incoming turn records', () => {
        const { result } = renderHook(() => useTurnTimings());
        const t1 = makeTurn();
        const t2 = makeTurn();

        act(() => {
            fireTurnTiming(t1);
        });
        act(() => {
            fireTurnTiming(t2);
        });

        expect(result.current.turns).toHaveLength(2);
        expect(result.current.turns[0].turn_id).toBe(t1.turn_id);
        expect(result.current.turns[1].turn_id).toBe(t2.turn_id);
    });

    it('keeps only last 5 turns', () => {
        const { result } = renderHook(() => useTurnTimings());

        const turns = Array.from({ length: 7 }, () => makeTurn());
        act(() => {
            for (const t of turns) fireTurnTiming(t);
        });

        expect(result.current.turns).toHaveLength(5);
        // First 2 should be evicted
        expect(result.current.turns[0].turn_id).toBe(turns[2].turn_id);
        expect(result.current.turns[4].turn_id).toBe(turns[6].turn_id);
    });

    it('unsubscribes on unmount', () => {
        const unsub = vi.fn();
        vi.mocked(subscribeTurnTimingStream).mockReturnValueOnce(unsub);

        const { unmount } = renderHook(() => useTurnTimings());
        unmount();

        expect(unsub).toHaveBeenCalledTimes(1);
    });
});
