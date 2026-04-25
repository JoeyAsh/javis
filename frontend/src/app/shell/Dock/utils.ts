import type { AppOrbState } from '@common/types';

export function toDisplayState(state: AppOrbState): AppOrbState {
    if (state === 'follow_up') return 'listening';
    return state;
}
