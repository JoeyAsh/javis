import { createSelector } from '@reduxjs/toolkit';
import type { RootState } from '@app/store';
import type { OrbState, AppOrbState } from '@common/types';

export const selectOrbBase = (state: RootState): OrbState => state.orbState.base;

export const selectIsWorking = (state: RootState): boolean =>
    state.orbState.activeToolCall !== null;

export const selectConnected = (state: RootState): boolean => state.orbState.connected;

/**
 * Derives the effective AppOrbState for consumption by App.tsx.
 *
 * Priority:
 *   1. 'working' — when any tool call is active.
 *   2. base state from backend.
 *
 * The follow_up → listening mapping lives inside the UI layer (display only),
 * not here — this selector only manages data-layer state derivation.
 */
export const selectAppOrbState = createSelector(
    selectIsWorking,
    selectOrbBase,
    (isWorking, base): AppOrbState => {
        if (isWorking) return 'working';
        return base;
    },
);
