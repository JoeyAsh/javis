import { createSelector } from '@reduxjs/toolkit';
import type { RootState } from '@app';
import type { NarrationItem, NarrationEngineState, SourceEntry } from './types';

const selectActivitySlice = (state: RootState) => state.activity;

export const selectActivityState = createSelector(
    selectActivitySlice,
    (slice): NarrationEngineState => slice.state,
);

export const selectQuietUntil = createSelector(
    selectActivitySlice,
    (slice): string | null => slice.quietUntil,
);

export const selectActivitySources = createSelector(
    selectActivitySlice,
    (slice): Record<string, SourceEntry> => slice.sources,
);

export const selectActivityHistory = createSelector(
    selectActivitySlice,
    (slice): NarrationItem[] => slice.history,
);

export const selectActivityHasLiveData = createSelector(
    selectActivitySlice,
    (slice): boolean => slice.hasLiveData,
);
