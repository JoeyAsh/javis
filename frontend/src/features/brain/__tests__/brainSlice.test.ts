// === FILE: frontend/src/features/brain/__tests__/brainSlice.test.ts ===
/**
 * Tests for brainSlice — covers the reducer, actions, and mergeEvents logic.
 *
 * Spec ACs addressed here:
 *   - brainInspectorReceived merges + dedupes by id, keeps last 50 sorted desc by ts
 *   - brainInspectorReceived replaces voiceComposerStatus and counts24h
 *   - setKindFilter / setSinceFilter round-trip
 */

import { describe, it, expect } from 'vitest';
import brainReducer, {
    brainInspectorReceived,
    setKindFilter,
    setSinceFilter,
    type BrainState,
} from '../brainSlice';
import type { BrainInspectorPayload, DeviceEvent, LedgerKind } from '../types';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeEvent(id: number, kind: LedgerKind = 'wake_word', tsOffset = 0): DeviceEvent {
    return {
        id,
        correlation_id: `corr-${id}`,
        kind,
        source: 'voice',
        ts: new Date(1_700_000_000_000 + tsOffset * 1000).toISOString(),
        payload: {},
    };
}

function makePayload(events: DeviceEvent[]): BrainInspectorPayload {
    return {
        voice_composer_status: {
            last_compose_ts: '2026-04-27T10:00:00.000Z',
            last_salutation: 'Sir',
        },
        ledger_recent: events,
        ledger_count_24h: {
            tts_emitted: 5,
            wake_word: 3,
        },
    };
}

const initialState: BrainState = {
    voiceComposerStatus: { last_compose_ts: null, last_salutation: null },
    recent: [],
    counts24h: {},
    filter: { kinds: [], sinceMs: null },
    lastInspectorTs: null,
};

// ---------------------------------------------------------------------------
// Initial state
// ---------------------------------------------------------------------------

describe('brainSlice initial state', () => {
    it('starts with empty recent array and null filters', () => {
        const state = brainReducer(undefined, { type: '@@INIT' });
        expect(state.recent).toEqual([]);
        expect(state.filter.kinds).toEqual([]);
        expect(state.filter.sinceMs).toBeNull();
        expect(state.lastInspectorTs).toBeNull();
    });

    it('starts with null voice composer status', () => {
        const state = brainReducer(undefined, { type: '@@INIT' });
        expect(state.voiceComposerStatus.last_compose_ts).toBeNull();
        expect(state.voiceComposerStatus.last_salutation).toBeNull();
    });
});

// ---------------------------------------------------------------------------
// brainInspectorReceived — merge & dedup
// ---------------------------------------------------------------------------

describe('brainInspectorReceived', () => {
    it('adds new events to an empty state', () => {
        const events = [makeEvent(1), makeEvent(2), makeEvent(3)];
        const state = brainReducer(initialState, brainInspectorReceived(makePayload(events)));
        expect(state.recent).toHaveLength(3);
    });

    it('deduplicates by id — same id is replaced with the incoming version', () => {
        const existing = makeEvent(1, 'wake_word', 100);
        const stateWithOne = brainReducer(
            initialState,
            brainInspectorReceived(makePayload([existing])),
        );

        // Incoming payload has updated version of id=1 with different kind.
        const updated: DeviceEvent = { ...existing, kind: 'tts_emitted' };
        const stateAfterUpdate = brainReducer(
            stateWithOne,
            brainInspectorReceived(makePayload([updated])),
        );

        expect(stateAfterUpdate.recent).toHaveLength(1);
        expect(stateAfterUpdate.recent[0].kind).toBe('tts_emitted');
    });

    it('merges incoming events with existing without duplicating shared ids', () => {
        const ev1 = makeEvent(1, 'wake_word', 100);
        const ev2 = makeEvent(2, 'tts_emitted', 200);
        const ev3 = makeEvent(3, 'mcp_call', 300);

        // Seed state with ev1 and ev2.
        let state = brainReducer(initialState, brainInspectorReceived(makePayload([ev1, ev2])));
        // Now add ev2 (duplicate) and ev3 (new).
        state = brainReducer(state, brainInspectorReceived(makePayload([ev2, ev3])));

        expect(state.recent).toHaveLength(3);
        const ids = state.recent.map((e) => e.id).sort((a, b) => a - b);
        expect(ids).toEqual([1, 2, 3]);
    });

    it('sorts events descending by ts (newest first)', () => {
        // Build events with different timestamps: ev3 is newest, ev1 is oldest.
        const ev1 = makeEvent(1, 'wake_word', 0);    // ts = T+0
        const ev2 = makeEvent(2, 'mcp_call', 1000);  // ts = T+1000s
        const ev3 = makeEvent(3, 'tts_emitted', 2000); // ts = T+2000s

        const state = brainReducer(
            initialState,
            brainInspectorReceived(makePayload([ev1, ev2, ev3])),
        );

        // First element should have the latest ts.
        expect(state.recent[0].id).toBe(3);
        expect(state.recent[2].id).toBe(1);
    });

    it('caps recent list at 50 events after merge', () => {
        // First fill with 48 events.
        const firstBatch = Array.from({ length: 48 }, (_, i) =>
            makeEvent(i + 1, 'orb_state', i),
        );
        let state = brainReducer(
            initialState,
            brainInspectorReceived(makePayload(firstBatch)),
        );

        // Add 5 more new events (total would be 53 → capped at 50).
        const secondBatch = Array.from({ length: 5 }, (_, i) =>
            makeEvent(100 + i, 'tts_emitted', 100 + i),
        );
        state = brainReducer(state, brainInspectorReceived(makePayload(secondBatch)));

        expect(state.recent.length).toBeLessThanOrEqual(50);
    });

    it('replaces voiceComposerStatus from payload', () => {
        const payload: BrainInspectorPayload = {
            voice_composer_status: {
                last_compose_ts: '2026-04-27T12:00:00.000Z',
                last_salutation: 'Sir',
            },
            ledger_recent: [],
            ledger_count_24h: {},
        };
        const state = brainReducer(initialState, brainInspectorReceived(payload));
        expect(state.voiceComposerStatus.last_compose_ts).toBe('2026-04-27T12:00:00.000Z');
        expect(state.voiceComposerStatus.last_salutation).toBe('Sir');
    });

    it('replaces counts24h from payload', () => {
        const payload: BrainInspectorPayload = {
            voice_composer_status: { last_compose_ts: null, last_salutation: null },
            ledger_recent: [],
            ledger_count_24h: { tts_emitted: 42, wake_word: 7 },
        };
        const state = brainReducer(initialState, brainInspectorReceived(payload));
        expect(state.counts24h.tts_emitted).toBe(42);
        expect(state.counts24h.wake_word).toBe(7);
    });

    it('updates lastInspectorTs on every dispatch', () => {
        const state = brainReducer(
            initialState,
            brainInspectorReceived(makePayload([])),
        );
        expect(state.lastInspectorTs).not.toBeNull();
        expect(typeof state.lastInspectorTs).toBe('string');
    });
});

// ---------------------------------------------------------------------------
// setKindFilter
// ---------------------------------------------------------------------------

describe('setKindFilter', () => {
    it('sets the kinds filter', () => {
        const kinds: LedgerKind[] = ['tts_emitted', 'mcp_call'];
        const state = brainReducer(initialState, setKindFilter(kinds));
        expect(state.filter.kinds).toEqual(kinds);
    });

    it('accepts an empty array (all kinds)', () => {
        const preloaded: BrainState = {
            ...initialState,
            filter: { kinds: ['wake_word'], sinceMs: null },
        };
        const state = brainReducer(preloaded, setKindFilter([]));
        expect(state.filter.kinds).toEqual([]);
    });

    it('round-trips: set then clear', () => {
        let state = brainReducer(initialState, setKindFilter(['error', 'barge_in']));
        state = brainReducer(state, setKindFilter([]));
        expect(state.filter.kinds).toEqual([]);
    });
});

// ---------------------------------------------------------------------------
// setSinceFilter
// ---------------------------------------------------------------------------

describe('setSinceFilter', () => {
    it('sets a numeric sinceMs value', () => {
        const ts = Date.now() - 3_600_000;
        const state = brainReducer(initialState, setSinceFilter(ts));
        expect(state.filter.sinceMs).toBe(ts);
    });

    it('accepts null to clear the filter', () => {
        const preloaded: BrainState = {
            ...initialState,
            filter: { kinds: [], sinceMs: Date.now() - 1000 },
        };
        const state = brainReducer(preloaded, setSinceFilter(null));
        expect(state.filter.sinceMs).toBeNull();
    });

    it('round-trips: set then clear', () => {
        const ts = 1_700_000_000_000;
        let state = brainReducer(initialState, setSinceFilter(ts));
        expect(state.filter.sinceMs).toBe(ts);
        state = brainReducer(state, setSinceFilter(null));
        expect(state.filter.sinceMs).toBeNull();
    });
});
