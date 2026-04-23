import type { ReactElement } from 'react';
import type { TransportControlsProps } from './TransportControls.types';
import styles from './TransportControls.module.css';

export function TransportControls({ track, onCmd }: TransportControlsProps): ReactElement {
    return (
        <div className={styles.controls} data-no-drag>
            <button
                type="button"
                aria-label="Previous"
                className={styles.btn}
                onClick={() => onCmd('prev')}
            >
                <svg viewBox="0 0 24 24" fill="currentColor">
                    <polygon points="18,5 8,12 18,19" />
                    <rect x="6" y="5" width="2" height="14" />
                </svg>
            </button>
            <button
                type="button"
                aria-label={track.playing ? 'Pause' : 'Play'}
                className={`${styles.btn} ${styles.btnPrimary}`}
                onClick={() => onCmd(track.playing ? 'pause' : 'play')}
            >
                {track.playing ? (
                    <svg viewBox="0 0 24 24" fill="currentColor">
                        <rect x="6" y="4" width="4" height="16" />
                        <rect x="14" y="4" width="4" height="16" />
                    </svg>
                ) : (
                    <svg viewBox="0 0 24 24" fill="currentColor">
                        <polygon points="6,3 21,12 6,21" />
                    </svg>
                )}
            </button>
            <button
                type="button"
                aria-label="Next"
                className={styles.btn}
                onClick={() => onCmd('next')}
            >
                <svg viewBox="0 0 24 24" fill="currentColor">
                    <polygon points="6,5 16,12 6,19" />
                    <rect x="16" y="5" width="2" height="14" />
                </svg>
            </button>
        </div>
    );
}

export default TransportControls;
