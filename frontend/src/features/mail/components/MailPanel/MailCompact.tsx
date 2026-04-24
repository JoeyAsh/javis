import type { ReactElement } from 'react';
import { DraftPreview } from '../DraftPreview';
import type { MailCompactProps } from './MailCompact.types';
import styles from './MailPanel.module.css';

export function MailCompact({ messages, unreadCount, draft, sendFlash }: MailCompactProps): ReactElement {
    const vip = messages.filter((m) => m.isVip).length;
    const latest = messages[0];
    return (
        <div className={`${styles.compact}${sendFlash ? ` ${styles.flash}` : ''}`}>
            {draft && <DraftPreview draft={draft} />}
            <div className={styles.stats}>
                <span>
                    <span className={styles.count}>{unreadCount}</span>{' '}
                    <span className={styles.monoSmall}>ungelesen</span>
                </span>
                <span className={styles.separator}>·</span>
                <span>
                    <span className={styles.vip}>{vip}</span>{' '}
                    <span className={styles.monoSmall}>VIP</span>
                </span>
            </div>
            {latest && <div className={styles.sender}>{latest.sender}</div>}
        </div>
    );
}

export default MailCompact;
