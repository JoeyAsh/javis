import type { ReactElement } from 'react';
import { useSfx } from '@core/audio';
import { relativeTime } from '@common/utils/time';
import type { MailItemRowProps } from './MailItemRow.types';
import styles from './MailItemRow.module.css';

export function MailItemRow({ message, onClick }: MailItemRowProps): ReactElement {
    const { playOneShot } = useSfx();

    const handleClick = (): void => {
        playOneShot('click');
        onClick?.(message);
    };

    const timeClass = message.unread
        ? `${styles.time} ${styles.timeUnread}`
        : styles.time;

    return (
        <div
            className={styles.row}
            onClick={handleClick}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') handleClick();
            }}
        >
            <span className={timeClass}>{relativeTime(message.receivedAt)}</span>
            <div className={styles.body}>
                <div className={styles.subject}>{message.subject}</div>
                <div className={styles.sender}>{message.sender}</div>
            </div>
            {message.unread && <span className={styles.pill}>NEU</span>}
        </div>
    );
}

export default MailItemRow;
