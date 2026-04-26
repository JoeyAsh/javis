import type { ReactElement, MouseEvent } from 'react';
import { formatMs, isTrackResult } from '../../utils';
import type { TrackRowProps } from './TrackRow.types';

export function TrackRow({ track, index, onClick, onAddToQueue }: TrackRowProps): ReactElement {
    const handleClick = (): void => {
        onClick(track.uri);
    };

    const handleQueue = (e: MouseEvent): void => {
        e.stopPropagation();
        onAddToQueue?.(track.uri);
    };

    return (
        <div
            role="button"
            tabIndex={0}
            className="flex items-center gap-2 px-2 py-1.5 cursor-pointer hover:bg-[var(--surface-hover)] transition-colors duration-[var(--dur-fast)] group"
            onClick={handleClick}
            onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') handleClick();
            }}
        >
            {index !== undefined && (
                <span className="flex-shrink-0 w-5 text-right text-[9px] text-[var(--text-muted)] font-[var(--font)]">
                    {index + 1}
                </span>
            )}
            <span
                className="flex-shrink-0 w-7 h-7 flex items-center justify-center text-[9px] font-bold text-[var(--accent)] border border-[var(--accent)] font-[var(--font)] tracking-widest"
                aria-hidden="true"
            >
                {track.monogram}
            </span>
            <div className="flex flex-col min-w-0 flex-1">
                <span className="text-[11px] text-[var(--text)] font-[var(--font)] truncate">
                    {track.name}
                </span>
                <span className="text-[9px] text-[var(--text-muted)] font-[var(--font)] truncate">
                    {track.artist}
                </span>
            </div>
            {isTrackResult(track) && (
                <span className="flex-shrink-0 text-[9px] text-[var(--text-muted)] font-[var(--font)]">
                    {formatMs(track.durationMs)}
                </span>
            )}
            {onAddToQueue !== undefined && (
                <button
                    type="button"
                    aria-label="Add to queue"
                    className="flex-shrink-0 opacity-0 group-hover:opacity-100 text-[9px] px-1.5 py-0.5 border border-[var(--border)] text-[var(--text-muted)] hover:text-[var(--accent)] hover:border-[var(--accent)] font-[var(--font)] tracking-wide transition-all duration-[var(--dur-fast)]"
                    onClick={handleQueue}
                >
                    + Q
                </button>
            )}
        </div>
    );
}

export default TrackRow;
