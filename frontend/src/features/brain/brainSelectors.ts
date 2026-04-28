import { createSelector } from '@reduxjs/toolkit';
import type { RootState } from '@app';
import type {
    DeviceEvent,
    VoiceComposerStatus,
    LedgerKind,
    LedgerKindCounts,
} from './types';

const selectBrainSlice = (state: RootState) => state.brain;

export const selectVoiceComposerStatus = createSelector(
    selectBrainSlice,
    (slice): VoiceComposerStatus => slice.voiceComposerStatus,
);

export const selectCounts24h = createSelector(
    selectBrainSlice,
    (slice): LedgerKindCounts => slice.counts24h,
);

export const selectKindFilter = createSelector(
    selectBrainSlice,
    (slice): LedgerKind[] => slice.filter.kinds,
);

export const selectSinceFilter = createSelector(
    selectBrainSlice,
    (slice): number | null => slice.filter.sinceMs,
);

const selectAllRecent = createSelector(
    selectBrainSlice,
    (slice): DeviceEvent[] => slice.recent,
);

/**
 * Returns recent events filtered by the current kind whitelist and since-cutoff.
 * Empty kind list means "all kinds".
 */
export const selectLedgerRecent = createSelector(
    selectAllRecent,
    selectKindFilter,
    selectSinceFilter,
    (events, kinds, sinceMs): DeviceEvent[] => {
        let filtered = events;
        if (kinds.length > 0) {
            filtered = filtered.filter((e) => kinds.includes(e.kind));
        }
        if (sinceMs !== null) {
            const cutoff = new Date(sinceMs).toISOString();
            filtered = filtered.filter((e) => e.ts >= cutoff);
        }
        return filtered;
    },
);
