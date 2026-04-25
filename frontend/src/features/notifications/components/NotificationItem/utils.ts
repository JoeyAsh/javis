import type { NotificationSeverity } from '../../types';
import { relativeTime } from '@common/utils/time';
import styles from './NotificationItem.module.css';

export { relativeTime };

export function severityItemClass(sev: NotificationSeverity): string {
    switch (sev) {
        case 'urgent':
            return styles.itemUrgent;
        case 'warning':
            return styles.itemWarning;
        case 'info':
            return styles.itemInfo;
    }
}

export function severityTitleClass(sev: NotificationSeverity): string {
    switch (sev) {
        case 'urgent':
            return `${styles.title} ${styles.titleUrgent}`;
        case 'warning':
            return `${styles.title} ${styles.titleWarning}`;
        case 'info':
            return `${styles.title} ${styles.titleInfo}`;
    }
}
