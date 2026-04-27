import { createSelector } from '@reduxjs/toolkit';
import type { RootState } from '@app';
import type { BriefingPayload } from './types';

const FOUR_HOURS_MS = 4 * 60 * 60 * 1000;

export function selectBriefingPayload(state: RootState): BriefingPayload | null {
    return state.briefing.payload;
}

export function selectBriefingReceivedAt(state: RootState): string | null {
    return state.briefing.receivedAt;
}

export const selectBriefingIsFresh = createSelector(
    selectBriefingReceivedAt,
    (receivedAt): boolean => {
        if (receivedAt === null) return false;
        return Date.now() - new Date(receivedAt).getTime() < FOUR_HOURS_MS;
    },
);
