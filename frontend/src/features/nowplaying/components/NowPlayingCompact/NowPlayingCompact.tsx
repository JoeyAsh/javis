import type { ReactElement } from 'react';
import { useMockTicker } from '@common/hooks/useMockTicker';
import type { NowPlayingCompactProps } from './NowPlayingCompact.types';
import styles from './NowPlayingCompact.module.css';

export function NowPlayingCompact({ track, onCmd }: NowPlayingCompactProps): ReactElement {
    const tick = useMockTicker(1000, !track.playing);
    const progress = track.playing
        ? (track.progressMs + tick * 1000) % track.durationMs
        : track.progressMs;
    const pct = Math.min(100, (progress / track.durationMs) * 100);

    return (
        <div className={styles.compact}>
            <div className={styles.compactTitle}>{track.title}</div>
            <div className={styles.compactArtist}>{track.artist}</div>
            <div className={styles.compactRow}>
                <div className={styles.compactBar}>
                    <div className={styles.compactBarFill} style={{ width: `${pct}%` }} />
                </div>
                <button
                    type="button"
                    aria-label={track.playing ? 'Pause' : 'Play'}
                    data-no-drag
                    className={styles.compactPlayBtn}
                    onClick={() => onCmd(track.playing ? 'pause' : 'play')}
                >
                    {track.playing ? '⏸' : '▶'}
                </button>
            </div>
        </div>
    );
}

export default NowPlayingCompact;
