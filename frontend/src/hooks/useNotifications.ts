import { useEffect, useState } from 'react';
import { subscribeNotificationStream } from './useWebSocket';
import type { HudNotification } from '../types';

const MAX_NOTIFICATIONS = 20;

export interface UseNotificationsReturn {
  /** Newest first. */
  notifications: HudNotification[];
  /** True once at least one live notification has arrived. */
  isLive: boolean;
}

/**
 * Subscribes to the backend `notification` WS stream. Maintains a rolling
 * buffer (newest first). Consumers fall back to mock data when `!isLive`.
 */
export function useNotifications(): UseNotificationsReturn {
  const [notifications, setNotifications] = useState<HudNotification[]>([]);
  const [isLive, setIsLive] = useState(false);

  useEffect(() => {
    const unsubscribe = subscribeNotificationStream((payload) => {
      setIsLive(true);
      setNotifications((prev) => {
        const next: HudNotification = {
          id: payload.id,
          severity: payload.severity,
          title: payload.title,
          detail: payload.detail ?? '',
          timestamp: payload.timestamp ?? new Date().toISOString(),
        };
        // Dedup by id, prepend newest, cap length.
        const filtered = prev.filter((n) => n.id !== next.id);
        const combined = [next, ...filtered];
        return combined.length > MAX_NOTIFICATIONS
          ? combined.slice(0, MAX_NOTIFICATIONS)
          : combined;
      });
    });
    return unsubscribe;
  }, []);

  return { notifications, isLive };
}

export default useNotifications;
