import type { AppOrbState } from '@common/types';

/** follow_up renders visually as listening */
export function toDisplayOrbState(state: AppOrbState): AppOrbState {
    if (state === 'follow_up') return 'listening';
    return state;
}
