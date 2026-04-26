import { useRef } from 'react';
import type { CSSProperties, ReactElement, ChangeEvent } from 'react';
import type { TransportControlsProps } from './TransportControls.types';
import styles from './TransportControls.module.css';

export function TransportControls({ track, onCmd, volume, onVolume }: TransportControlsProps): ReactElement {
    const lastVolumeRef = useRef<number>(volume > 0 ? volume : 50);
    const isMuted = volume === 0;

    function handleMuteToggle(): void {
        if (isMuted) {
            const restore = lastVolumeRef.current > 0 ? lastVolumeRef.current : 50;
            onVolume(restore);
        } else {
            lastVolumeRef.current = volume;
            onVolume(0);
        }
    }

    function handleSliderChange(e: ChangeEvent<HTMLInputElement>): void {
        const next = Number(e.target.value);
        if (next > 0) {
            lastVolumeRef.current = next;
        }
        onVolume(next);
    }

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
            <button
                type="button"
                aria-label={isMuted ? 'Unmute' : 'Mute'}
                className={styles.btn}
                data-no-drag
                onClick={handleMuteToggle}
            >
                {isMuted ? (
                    <svg viewBox="0 0 24 24" fill="currentColor">
                        <polygon points="4,9 4,15 8,15 13,20 13,4 8,9" />
                        <line x1="17" y1="9" x2="23" y2="15" stroke="currentColor" strokeWidth="2" strokeLinecap="square" />
                        <line x1="23" y1="9" x2="17" y2="15" stroke="currentColor" strokeWidth="2" strokeLinecap="square" />
                    </svg>
                ) : (
                    <svg viewBox="0 0 24 24" fill="currentColor">
                        <polygon points="4,9 4,15 8,15 13,20 13,4 8,9" />
                        <path d="M16 9 Q19 12 16 15" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="square" />
                        <path d="M18 7 Q23 12 18 17" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="square" />
                    </svg>
                )}
            </button>
            <input
                type="range"
                min={0}
                max={100}
                value={volume}
                aria-label="Volume"
                data-no-drag
                className={styles.volumeSlider}
                style={{ '--vol-pct': `${volume}%` } as CSSProperties}
                onChange={handleSliderChange}
            />
        </div>
    );
}

export default TransportControls;
