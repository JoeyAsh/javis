import type { ReactElement } from 'react';
import { NotificationItem } from '../NotificationItem';
import type { NotificationsExpandedProps } from './NotificationsExpanded.types';
import styles from './NotificationsPanel.module.css';

export function NotificationsExpanded({ notifications }: NotificationsExpandedProps): ReactElement {
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

export default NotificationsExpanded;
