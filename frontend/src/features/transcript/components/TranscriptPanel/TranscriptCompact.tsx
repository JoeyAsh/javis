import { useMemo } from 'react';
import type { ReactElement } from 'react';
import type { TranscriptCompactProps } from './TranscriptCompact.types';
import styles from './TranscriptPanel.module.css';

export function TranscriptCompact({ turns }: TranscriptCompactProps): ReactElement {
    const lastJarvis = useMemo(
        () => [...turns].reverse().find((t) => t.role === 'jarvis'),
        [turns],
    );

    if (!lastJarvis) {
        return (
            <div className={styles.compact}>
                <span className={styles.empty}>Kein Transcript</span>
            </div>
        );
    }

    const d = new Date(lastJarvis.at);
    const time = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;

    return (
        <div className={styles.compact}>
            <div className={styles.compactHeader}>
                <span className={styles.compactRole}>JARVIS</span>
                <span className={styles.compactTime}>{time}</span>
            </div>
            <div className={styles.compactText} title={lastJarvis.text}>
                {lastJarvis.text}
            </div>
        </div>
    );
}

export default TranscriptCompact;
