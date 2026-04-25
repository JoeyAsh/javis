import type { ReactElement } from 'react';
import { formatMs } from '../../utils';
import type { ProgressBarProps } from './ProgressBar.types';
import { useLiveProgress } from './useLiveProgress';
import styles from './ProgressBar.module.css';

export function ProgressBar({ track }: ProgressBarProps): ReactElement {
    const progress = useLiveProgress(track.playing, track.progressMs, track.durationMs);
    const pct = Math.min(100, (progress / track.durationMs) * 100);

    return (
        <div className={styles.progress}>
            <div className={styles.bar}>
                <div className={styles.barFill} style={{ width: `${pct}%` }} />
            </div>
            <div className={styles.times}>
                <span>{formatMs(progress)}</span>
                <span>{formatMs(track.durationMs)}</span>
            </div>
        </div>
    );
}

export default ProgressBar;
