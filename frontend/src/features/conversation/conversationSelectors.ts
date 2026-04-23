import type { RootState } from '@app/store';

export const selectFollowUpActive = (state: RootState): boolean =>
    state.conversation.followUpActive;

export const selectFollowUpSecondsRemaining = (state: RootState): number =>
    state.conversation.followUpSecondsRemaining;
