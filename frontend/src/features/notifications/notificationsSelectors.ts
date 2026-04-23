import type { RootState } from '@app';
import type { HudNotification } from './types';

export function selectNotifications(state: RootState): HudNotification[] {
    return state.notifications.items;
}

export function selectNotificationsHasLiveData(state: RootState): boolean {
    return state.notifications.hasLiveData;
}
