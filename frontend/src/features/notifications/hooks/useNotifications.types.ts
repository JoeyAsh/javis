import type { HudNotification } from '../types';

export interface UseNotificationsReturn {
    notifications: HudNotification[];
    hasLiveData: boolean;
}
