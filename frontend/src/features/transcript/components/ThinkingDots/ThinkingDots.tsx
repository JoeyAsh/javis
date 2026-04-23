import type { ReactElement } from 'react';
import styles from './ThinkingDots.module.css';

/**
 * ThinkingDots — animated 3-dot indicator shown while orbState === 'thinking'.
 * Rendered inside a transcript turn bubble matching the prototype blink pattern.
 */
export function ThinkingDots(): ReactElement {
    return (
        <div className="transcript-turn transcript-turn--jarvis">
            <div className="transcript-turn__block">
                <div className="transcript-turn__meta">
                    <span className="transcript-turn__meta-role">J.</span>
                    <span className="transcript-turn__meta-time">…</span>
                </div>
                <div className="transcript-turn__bubble--jarvis">
                    <span className={styles.container}>
                        <i className={`${styles.dot} ${styles.dot1}`} />
                        <i className={`${styles.dot} ${styles.dot2}`} />
                        <i className={`${styles.dot} ${styles.dot3}`} />
                    </span>
                </div>
            </div>
        </div>
    );
}

export default ThinkingDots;
