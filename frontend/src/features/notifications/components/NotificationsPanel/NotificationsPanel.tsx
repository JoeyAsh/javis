/**
 * NotificationsPanel — panel body for HUD notifications.
 * Data from Redux notifications slice via useNotifications hook.
 */
import { useEffect, useRef, useState } from 'react';
import type { ReactElement } from 'react';
import { usePanelAvailable } from '@app/providers/PanelAvailabilityProvider';
import { useNotifications } from '../../hooks/useNotifications';
import { NotificationsCompact } from './NotificationsCompact';
import { NotificationsExpanded } from './NotificationsExpanded';
import type { HudNotification } from '../../types';
import type { NotificationsPanelProps } from './NotificationsPanel.types';
import { AVAILABILITY_TIMEOUT_MS } from './constants';
import styles from './NotificationsPanel.module.css';

/**
 * NotificationsPanel body — severity-coloured notification rows.
 * Accepts optional `notifications` prop for testing.
 * Shows unavailable-state if no payload arrives within 10 s.
 */
export function NotificationsPanel({
    notifications: notificationsProp,
    mode = 'expanded',
}: NotificationsPanelProps): ReactElement {
    const { notifications: live, hasLiveData } = useNotifications();
    const [backendAvailable, setBackendAvailable] = useState(true);
    const availabilityTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    usePanelAvailable('notifications', backendAvailable || hasLiveData);

    useEffect(() => {
        if (notificationsProp !== undefined) return;
        availabilityTimerRef.current = setTimeout(() => {
            setBackendAvailable(false);
        }, AVAILABILITY_TIMEOUT_MS);
        return () => {
            if (availabilityTimerRef.current) clearTimeout(availabilityTimerRef.current);
        };
    }, [notificationsProp]);

    // Cancel availability timer once live data arrives.
    useEffect(() => {
        if (hasLiveData && availabilityTimerRef.current) {
            clearTimeout(availabilityTimerRef.current);
            setBackendAvailable(true);
        }
    }, [hasLiveData]);

    const source: HudNotification[] = notificationsProp !== undefined ? notificationsProp : live;

    // Backend not available — show fallback.
    if (notificationsProp === undefined && !backendAvailable && !hasLiveData) {
        return (
            <div className={styles.panel}>
                <span className={styles.empty}>Benachrichtigungen momentan nicht verfügbar</span>
            </div>
        );
    }

    return mode === 'compact' ? (
        <NotificationsCompact notifications={source} />
    ) : (
        <NotificationsExpanded notifications={source} />
    );
}

export default NotificationsPanel;
