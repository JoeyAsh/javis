/**
 * NotificationsPanel — panel body for HUD notifications.
 * Data from Redux notifications slice via useNotifications hook.
 */
import { useEffect, useRef, useState } from 'react';
import type { ReactElement } from 'react';
import { usePanelAvailable } from '../../../../contexts/PanelAvailability';
import { useNotifications } from '../../hooks/useNotifications';
import { NotificationItem } from '../NotificationItem';
import type { HudNotification, NotificationSeverity } from '../../types';
import type { NotificationsPanelProps } from './NotificationsPanel.types';
import styles from './NotificationsPanel.module.css';

const AVAILABILITY_TIMEOUT_MS = 10_000;

function severityDotStyle(sev: NotificationSeverity): string {
    switch (sev) {
        case 'urgent':
            return 'var(--error, #e05c5c)';
        case 'warning':
            return 'var(--warning, #e0a85c)';
        case 'info':
            return 'var(--accent-bright)';
    }
}

function severityTitleStyle(sev: NotificationSeverity): string {
    switch (sev) {
        case 'urgent':
            return 'var(--error, #e05c5c)';
        case 'warning':
            return 'var(--warning, #e0a85c)';
        case 'info':
            return 'var(--accent-bright)';
    }
}

// ---- Compact mode ----

function NotificationsCompact({
    notifications,
}: {
    notifications: HudNotification[];
}): ReactElement {
    const top = notifications[0];
    const remaining = Math.max(0, notifications.length - 1);

    if (!top) {
        return (
            <div className={styles.compact}>
                <span className={styles.empty}>Keine aktiven Benachrichtigungen</span>
            </div>
        );
    }

    return (
        <div className={styles.compact}>
            <div className={styles.compactRow}>
                <span
                    aria-hidden
                    className={styles.dot}
                    style={{ background: severityDotStyle(top.severity) }}
                />
                <span
                    className={styles.compactTitle}
                    style={{ color: severityTitleStyle(top.severity) }}
                >
                    {top.title}
                </span>
                {remaining > 0 && <span className={styles.badge}>+{remaining}</span>}
            </div>
            <div className={styles.compactDetail}>{top.detail}</div>
        </div>
    );
}

// ---- Expanded mode ----

function NotificationsExpanded({
    notifications,
}: {
    notifications: HudNotification[];
}): ReactElement {
    if (notifications.length === 0) {
        return (
            <div className={styles.panel}>
                <span className={styles.empty}>Keine aktiven Benachrichtigungen</span>
            </div>
        );
    }

    return (
        <div className={styles.panel}>
            {notifications.map((n) => (
                <NotificationItem key={n.id} notification={n} />
            ))}
        </div>
    );
}

// ---- Main export ----

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
