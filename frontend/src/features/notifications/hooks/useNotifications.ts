import { useAppSelector } from '@app';
import { useStreamNotificationsQuery } from '../notificationsApi';
import { selectNotifications, selectNotificationsHasLiveData } from '../notificationsSelectors';
import type { UseNotificationsReturn } from './useNotifications.types';

export function useNotifications(): UseNotificationsReturn {
    useStreamNotificationsQuery();

    const notifications = useAppSelector(selectNotifications);
    const hasLiveData = useAppSelector(selectNotificationsHasLiveData);

    return { notifications, hasLiveData };
}
