/**
 * NotificationItem — a single notification row.
 * Matches prototype `.nf` pattern: severity-coloured left border,
 * source header + timestamp, detail text.
 */
import type { ReactElement } from 'react';
import type { HudNotification, NotificationSeverity } from '../../../types';
import './NotificationsPanel.css';

export interface NotificationItemProps {
    notification: HudNotification;
    onClick?: (id: string) => void;
}

function severityClass(sev: NotificationSeverity): string {
    switch (sev) {
        case 'urgent':
            return 'notif-item--urgent';
        case 'warning':
            return 'notif-item--warning';
        case 'info':
            return 'notif-item--info';
    }
}

function titleClass(sev: NotificationSeverity): string {
    switch (sev) {
        case 'urgent':
            return 'notif-item__title notif-item__title--urgent';
        case 'warning':
            return 'notif-item__title notif-item__title--warning';
        case 'info':
            return 'notif-item__title notif-item__title--info';
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
            className={`notif-item ${severityClass(notification.severity)}`}
            onClick={handleClick}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') handleClick();
            }}
        >
            <div className="notif-item__header">
                <span className={titleClass(notification.severity)}>{notification.title}</span>
                <span className="notif-item__time">{relativeTime(notification.timestamp)}</span>
            </div>
            <div className="notif-item__detail">{notification.detail}</div>
        </div>
    );
}

export default NotificationItem;
