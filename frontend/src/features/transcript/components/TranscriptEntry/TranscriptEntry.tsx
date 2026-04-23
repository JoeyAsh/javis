import type { ReactElement } from 'react';
import type { TranscriptEntryProps } from './TranscriptEntry.types';
import styles from './TranscriptEntry.module.css';

function formatTime(iso: string): string {
    const d = new Date(iso);
    return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

export function TranscriptEntry({ turn }: TranscriptEntryProps): ReactElement {
    const isUser = turn.role === 'user';
    const rowClass = `${styles.turn}${isUser ? ` ${styles.turnUser}` : ''}`;
    const bubbleClass = isUser ? styles.bubbleUser : styles.bubbleJarvis;

    return (
        <div className={rowClass}>
            <div className={styles.block}>
                <div className={styles.meta}>
                    {!isUser && (
                        <span className={styles.metaRole}>J.</span>
                    )}
                    {isUser ? 'You ' : ''}
                    <span>{formatTime(turn.at)}</span>
                </div>
                <div className={bubbleClass}>{turn.text}</div>
            </div>
        </div>
    );
}

export default TranscriptEntry;
