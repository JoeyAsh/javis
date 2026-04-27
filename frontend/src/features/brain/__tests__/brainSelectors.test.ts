// === FILE: frontend/src/features/brain/__tests__/brainSelectors.test.ts ===
/**
 * Tests for brainSelectors — covers selectLedgerRecent filtering and memoisation.
 *
 * Pure function tests: no rendering, no store provider.
 */

import { describe, it, expect } from 'vitest';
import {
    selectLedgerRecent,
    selectVoiceComposerStatus,
    selectCounts24h,
    selectKindFilter,
    selectSinceFilter,
} from '../brainSelectors';
import type { BrainState } from '../brainSlice';
import type { DeviceEvent, LedgerKind } from '../types';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeEvent(
    id: number,
    kind: LedgerKind = 'wake_word',
    tsMs = 1_700_000_000_000,
): DeviceEvent {
    return {
        id,
        correlation_id: null,
        kind,
        source: 'voice',
        ts: new Date(tsMs).toISOString(),
        payload: {},
    };
}

function makeState(overrides: Partial<BrainState> = {}): { brain: BrainState } {
    const base: BrainState = {
        voiceComposerStatus: { last_compose_ts: null, last_salutation: null },
        recent: [],
        counts24h: {},
        filter: { kinds: [], sinceMs: null },
        lastInspectorTs: null,
    };
    return { brain: { ...base, ...overrides } };
}

// ---------------------------------------------------------------------------
// selectLedgerRecent — kind whitelist filter
// ---------------------------------------------------------------------------

describe('selectLedgerRecent — kind filter', () => {
    it('returns all events when kinds filter is empty', () => {
        const events = [
            makeEvent(1, 'wake_word'),
            makeEvent(2, 'tts_emitted'),
            makeEvent(3, 'mcp_call'),
        ];
        const state = makeState({ recent: events, filter: { kinds: [], sinceMs: null } });
        expect(selectLedgerRecent(state)).toHaveLength(3);
    });

    it('filters to specified kinds only', () => {
        const events = [
            makeEvent(1, 'wake_word'),
            makeEvent(2, 'tts_emitted'),
            makeEvent(3, 'mcp_call'),
            makeEvent(4, 'tts_emitted'),
        ];
        const state = makeState({
            recent: events,
            filter: { kinds: ['tts_emitted'], sinceMs: null },
        });
        const result = selectLedgerRecent(state);
        expect(result).toHaveLength(2);
        result.forEach((e) => expect(e.kind).toBe('tts_emitted'));
    });

    it('returns empty array when no events match the kind filter', () => {
        const events = [makeEvent(1, 'wake_word'), makeEvent(2, 'mcp_call')];
        const state = makeState({
            recent: events,
            filter: { kinds: ['error'], sinceMs: null },
        });
        expect(selectLedgerRecent(state)).toHaveLength(0);
    });

    it('handles multiple kinds in the whitelist', () => {
        const events = [
            makeEvent(1, 'wake_word'),
            makeEvent(2, 'tts_emitted'),
            makeEvent(3, 'error'),
            makeEvent(4, 'barge_in'),
        ];
        const state = makeState({
            recent: events,
            filter: { kinds: ['tts_emitted', 'error'], sinceMs: null },
        });
        const result = selectLedgerRecent(state);
        expect(result).toHaveLength(2);
        const kinds = result.map((e) => e.kind);
        expect(kinds).toContain('tts_emitted');
        expect(kinds).toContain('error');
    });
});

// ---------------------------------------------------------------------------
// selectLedgerRecent — sinceMs time filter
// ---------------------------------------------------------------------------

describe('selectLedgerRecent — since filter', () => {
    const BASE_MS = 1_700_000_000_000;

    it('returns all events when sinceMs is null', () => {
        const events = [
            makeEvent(1, 'wake_word', BASE_MS - 600_000),
            makeEvent(2, 'tts_emitted', BASE_MS - 300_000),
        ];
        const state = makeState({ recent: events, filter: { kinds: [], sinceMs: null } });
        expect(selectLedgerRecent(state)).toHaveLength(2);
    });

    it('filters out events older than sinceMs cutoff', () => {
        const cutoffMs = BASE_MS - 300_000; // 5 minutes ago
        const events = [
            makeEvent(1, 'wake_word', BASE_MS - 600_000),  // 10 min ago → excluded
            makeEvent(2, 'tts_emitted', BASE_MS - 100_000), // 100s ago → included
        ];
        const state = makeState({
            recent: events,
            filter: { kinds: [], sinceMs: cutoffMs },
        });
        const result = selectLedgerRecent(state);
        expect(result).toHaveLength(1);
        expect(result[0].id).toBe(2);
    });

    it('returns empty array when all events are before cutoff', () => {
        const events = [
            makeEvent(1, 'wake_word', BASE_MS - 3_600_000),
            makeEvent(2, 'mcp_call', BASE_MS - 7_200_000),
        ];
        const cutoffMs = BASE_MS - 1_000; // nearly now
        const state = makeState({
            recent: events,
            filter: { kinds: [], sinceMs: cutoffMs },
        });
        expect(selectLedgerRecent(state)).toHaveLength(0);
    });
});

// ---------------------------------------------------------------------------
// selectLedgerRecent — combined kind + since filter
// ---------------------------------------------------------------------------

describe('selectLedgerRecent — combined filters', () => {
    const BASE_MS = 1_700_000_000_000;

    it('applies both kind and time filters simultaneously', () => {
        const cutoffMs = BASE_MS - 300_000;
        const events = [
            makeEvent(1, 'tts_emitted', BASE_MS - 600_000), // old, matching kind → excluded
            makeEvent(2, 'tts_emitted', BASE_MS - 100_000), // recent, matching kind → included
            makeEvent(3, 'mcp_call', BASE_MS - 100_000),    // recent, wrong kind → excluded
        ];
        const state = makeState({
            recent: events,
            filter: { kinds: ['tts_emitted'], sinceMs: cutoffMs },
        });
        const result = selectLedgerRecent(state);
        expect(result).toHaveLength(1);
        expect(result[0].id).toBe(2);
    });
});

// ---------------------------------------------------------------------------
// Memoisation — same input reference → same output reference.
// ---------------------------------------------------------------------------

describe('selectLedgerRecent — memoisation', () => {
    it('returns the same reference when input state is unchanged', () => {
        const events = [makeEvent(1, 'wake_word')];
        const state = makeState({ recent: events, filter: { kinds: [], sinceMs: null } });

        const result1 = selectLedgerRecent(state);
        const result2 = selectLedgerRecent(state);

        // Strict reference equality — memoised by createSelector.
        expect(result1).toBe(result2);
    });

    it('returns a new reference when filter kinds change', () => {
        const events = [makeEvent(1, 'wake_word'), makeEvent(2, 'tts_emitted')];
        const stateA = makeState({ recent: events, filter: { kinds: [], sinceMs: null } });
        const stateB = makeState({
            recent: events,
            filter: { kinds: ['tts_emitted'], sinceMs: null },
        });

        const result1 = selectLedgerRecent(stateA);
        const result2 = selectLedgerRecent(stateB);

        // Different filter → different derived output.
        expect(result1).not.toBe(result2);
    });
});

// ---------------------------------------------------------------------------
// Other selectors — basic coverage
// ---------------------------------------------------------------------------

describe('selectVoiceComposerStatus', () => {
    it('returns the voice composer status slice', () => {
        const status = { last_compose_ts: '2026-04-27T10:00:00Z', last_salutation: 'Sir' };
        const state = makeState({ voiceComposerStatus: status });
        expect(selectVoiceComposerStatus(state)).toEqual(status);
    });

    it('is memoised — same input reference → same output', () => {
        const state = makeState();
        expect(selectVoiceComposerStatus(state)).toBe(selectVoiceComposerStatus(state));
    });
});

describe('selectCounts24h', () => {
    it('returns the counts24h slice', () => {
        const counts = { tts_emitted: 12, mcp_call: 5 };
        const state = makeState({ counts24h: counts });
        expect(selectCounts24h(state)).toEqual(counts);
    });
});

describe('selectKindFilter', () => {
    it('returns current kind filter array', () => {
        const kinds: LedgerKind[] = ['barge_in', 'error'];
        const state = makeState({ filter: { kinds, sinceMs: null } });
        expect(selectKindFilter(state)).toEqual(kinds);
    });
});

describe('selectSinceFilter', () => {
    it('returns the sinceMs value', () => {
        const ms = Date.now() - 3_600_000;
        const state = makeState({ filter: { kinds: [], sinceMs: ms } });
        expect(selectSinceFilter(state)).toBe(ms);
    });

    it('returns null when no filter is set', () => {
        const state = makeState({ filter: { kinds: [], sinceMs: null } });
        expect(selectSinceFilter(state)).toBeNull();
    });
});
