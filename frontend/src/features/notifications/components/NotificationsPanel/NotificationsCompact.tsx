import type { ReactElement } from 'react';
import type { NotificationsCompactProps } from './NotificationsCompact.types';
import { severityDotStyle, severityTitleStyle } from './utils';
import styles from './NotificationsPanel.module.css';

export function NotificationsCompact({ notifications }: NotificationsCompactProps): ReactElement {
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
                    style={{ background: severityDotStyle(top.severity) } as React.CSSProperties}
                />
                <span
                    className={styles.compactTitle}
                    style={{ color: severityTitleStyle(top.severity) } as React.CSSProperties}
                >
                    {top.title}
                </span>
                {remaining > 0 && <span className={styles.badge}>+{remaining}</span>}
            </div>
            <div className={styles.compactDetail}>{top.detail}</div>
        </div>
    );
}

export default NotificationsCompact;
