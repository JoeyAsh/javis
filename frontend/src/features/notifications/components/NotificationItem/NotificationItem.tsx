import type { ReactElement } from 'react';
import type { NotificationItemProps } from './NotificationItem.types';
import { relativeTime, severityItemClass, severityTitleClass } from './utils';
import styles from './NotificationItem.module.css';

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
