import type { ReactElement } from 'react';
import type { NotificationSeverity } from '../../types';
import type { NotificationItemProps } from './NotificationItem.types';
import styles from './NotificationItem.module.css';

function severityItemClass(sev: NotificationSeverity): string {
    switch (sev) {
        case 'urgent':
            return styles.itemUrgent;
        case 'warning':
            return styles.itemWarning;
        case 'info':
            return styles.itemInfo;
    }
}

function severityTitleClass(sev: NotificationSeverity): string {
    switch (sev) {
        case 'urgent':
            return `${styles.title} ${styles.titleUrgent}`;
        case 'warning':
            return `${styles.title} ${styles.titleWarning}`;
        case 'info':
            return `${styles.title} ${styles.titleInfo}`;
    }
}

function relativeTime(iso: string): string {
    const diff = Date.now() - new Date(iso).getTime();
    const secs = Math.floor(diff / 1000);
    if (secs < 60) return `${secs}s`;
    const mins = Math.floor(secs / 60);
    if (mins < 60) return `${mins}m`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h`;
    return `${Math.floor(hrs / 24)}d`;
}

export function NotificationItem({ notification, onClick }: NotificationItemProps): ReactElement {
    const handleClick = (): void => {
        onClick?.(notification.id);
    };

    return (
        <div
            className={`${styles.item} ${severityItemClass(notification.severity)}`}
            onClick={handleClick}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') handleClick();
            }}
        >
            <div className={styles.header}>
                <span className={severityTitleClass(notification.severity)}>
                    {notification.title}
                </span>
                <span className={styles.time}>{relativeTime(notification.timestamp)}</span>
            </div>
            <div className={styles.detail}>{notification.detail}</div>
        </div>
    );
}

export default NotificationItem;
