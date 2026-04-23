import type { ReactElement } from 'react';
import { relativeTime } from '../../utils';
import type { SelfFixEntryProps } from './SelfFixEntry.types';
import styles from './SelfFixEntry.module.css';

export function SelfFixEntry({ entry }: SelfFixEntryProps): ReactElement {
    const isInProgress = entry.status === 'in_progress';
    const entryClass = `list-item ${styles.entry}${isInProgress ? ` ${styles.entryInProgress}` : ''}`;
    const summaryClass = `${styles.summary}${isInProgress ? ` ${styles.summaryInProgress}` : ''}`;

    return (
        <div className={entryClass}>
            <div className={styles.header}>
                {isInProgress && <span className="pulse-dot" aria-hidden />}
                <span className={summaryClass}>{entry.summary}</span>
                <span className={styles.time}>{relativeTime(entry.startedAt)}</span>
            </div>
            <div className={styles.detail}>{entry.detail}</div>

            {entry.status === 'completed' && (
                <>
                    <div className={styles.commitRow}>
                        <span className={styles.sha}>{entry.commitSha ?? '——'}</span>
                        {entry.added !== undefined && (
                            <span className={styles.added}>+{entry.added}</span>
                        )}
                        {entry.removed !== undefined && (
                            <span className={styles.removed}>-{entry.removed}</span>
                        )}
                    </div>
                    <div className={styles.actions} data-no-drag>
                        <button type="button" className={`hud-iconbtn ${styles.btnAccept}`}>
                            ACCEPT
                        </button>
                        <button type="button" className={`hud-iconbtn ${styles.btnDiscard}`}>
                            DISCARD
                        </button>
                    </div>
                </>
            )}
        </div>
    );
}

export default SelfFixEntry;
