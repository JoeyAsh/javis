import type { ReactElement } from 'react';
import type { PlaylistRowProps } from './PlaylistRow.types';

export function PlaylistRow({ playlist, onClick }: PlaylistRowProps): ReactElement {
    const handleClick = (): void => {
        onClick(playlist);
    };

    return (
        <div
            role="button"
            tabIndex={0}
            className="flex items-center gap-2 px-2 py-1.5 cursor-pointer hover:bg-[var(--surface-hover)] transition-colors duration-[var(--dur-fast)]"
            onClick={handleClick}
            onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') handleClick();
            }}
        >
            <span
                className="flex-shrink-0 w-8 h-8 flex items-center justify-center text-[10px] font-bold text-[var(--accent)] border border-[var(--accent)] font-[var(--font)] tracking-widest"
                aria-hidden="true"
            >
                {playlist.monogram}
            </span>
            <div className="flex flex-col min-w-0 flex-1">
                <span className="text-[11px] text-[var(--text)] font-[var(--font)] truncate">
                    {playlist.name}
                </span>
                <span className="text-[9px] text-[var(--text-muted)] font-[var(--font)] tracking-wide">
                    {playlist.trackCount} TRACKS
                </span>
            </div>
        </div>
    );
}

export default PlaylistRow;
