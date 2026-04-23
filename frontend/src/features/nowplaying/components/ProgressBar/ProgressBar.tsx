import { useMemo } from 'react';
import type { ReactElement } from 'react';
import { useMockTicker } from '@common/hooks/useMockTicker';
import { formatMs } from '../../utils';
import type { ProgressBarProps } from './ProgressBar.types';
import styles from './ProgressBar.module.css';

/** Ticks forward 1 s per interval while the track is playing. */
function useLiveProgress(playing: boolean, progressMs: number, durationMs: number): number {
    const tick = useMockTicker(1000, !playing);
    return useMemo<number>(() => {
        if (!playing) return progressMs;
        return (progressMs + tick * 1000) % durationMs;
    }, [tick, playing, progressMs, durationMs]);
}

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
