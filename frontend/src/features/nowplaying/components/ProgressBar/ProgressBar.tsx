import { useCallback, useRef, useState } from 'react';
import type { CSSProperties, PointerEvent, ReactElement } from 'react';
import { formatMs } from '../../utils';
import type { ProgressBarProps } from './ProgressBar.types';
import { useLiveProgress } from './useLiveProgress';
import styles from './ProgressBar.module.css';

export function ProgressBar({ track, onSeek }: ProgressBarProps): ReactElement {
    const liveProgress = useLiveProgress(track.playing, track.progressMs, track.durationMs);

    // Local drag state — null when not dragging.
    const [dragPositionMs, setDragPositionMs] = useState<number | null>(null);
    const isDragging = dragPositionMs !== null;

    // During an active drag, prefer local drag position so time text mirrors cursor.
    const progress = isDragging ? dragPositionMs : liveProgress;
    const pct = Math.min(100, (progress / track.durationMs) * 100);

    const barRef = useRef<HTMLDivElement>(null);
    const isSeekable = onSeek !== undefined;

    const computePosition = useCallback(
        (clientX: number): number => {
            const bar = barRef.current;
            if (bar === null) return 0;
            const rect = bar.getBoundingClientRect();
            const ratio = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
            return Math.round(ratio * track.durationMs);
        },
        [track.durationMs],
    );

    const handlePointerDown = useCallback(
        (e: PointerEvent<HTMLDivElement>): void => {
            if (!isSeekable) return;
            e.currentTarget.setPointerCapture(e.pointerId);
            const pos = computePosition(e.clientX);
            setDragPositionMs(pos);
        },
        [isSeekable, computePosition],
    );

    const handlePointerMove = useCallback(
        (e: PointerEvent<HTMLDivElement>): void => {
            if (!isDragging || !isSeekable) return;
            const pos = computePosition(e.clientX);
            setDragPositionMs(pos);
        },
        [isDragging, isSeekable, computePosition],
    );

    const handlePointerUp = useCallback(
        (e: PointerEvent<HTMLDivElement>): void => {
            if (!isDragging || !isSeekable || onSeek === undefined) return;
            const pos = computePosition(e.clientX);
            setDragPositionMs(null);
            onSeek(pos);
        },
        [isDragging, isSeekable, onSeek, computePosition],
    );

    const handleClick = useCallback(
        (e: React.MouseEvent<HTMLDivElement>): void => {
            // Clicks are handled via pointerdown/pointerup when dragging; skip if dragging was active.
            if (!isSeekable || isDragging || onSeek === undefined) return;
            const pos = computePosition(e.clientX);
            onSeek(pos);
        },
        [isSeekable, isDragging, onSeek, computePosition],
    );

    return (
        <div className={styles.progress}>
            <div
                ref={barRef}
                className={styles.bar}
                data-seekable={isSeekable ? 'true' : 'false'}
                data-dragging={isDragging ? 'true' : 'false'}
                data-no-drag
                onPointerDown={handlePointerDown}
                onPointerMove={handlePointerMove}
                onPointerUp={handlePointerUp}
                onClick={handleClick}
            >
                <div
                    className={styles.barFill}
                    style={{ width: `${pct}%` } as CSSProperties}
                />
            </div>
            <div className={styles.times}>
                <span>{formatMs(progress)}</span>
                <span>{formatMs(track.durationMs)}</span>
            </div>
        </div>
    );
}

export default ProgressBar;
