import type { ReactElement } from 'react';
import { isSearchTrack, isSearchPlaylist, isSearchAlbum } from '../../utils';
import { TrackRow } from '../TrackRow';
import { PlaylistRow } from '../PlaylistRow';
import type { ResultGroupProps } from './ResultGroup.types';

export function ResultGroup({
    label,
    items,
    onTrackClick,
    onPlaylistClick,
    onAlbumClick,
    onArtistClick,
}: ResultGroupProps): ReactElement | null {
    if (items.length === 0) {
        return null;
    }

    return (
        <div className="mb-3">
            <div className="px-2 mb-1 text-[9px] text-[var(--text-muted)] font-[var(--font)] tracking-widest">
                {label}
            </div>
            {items.map((item) => {
                if (isSearchTrack(item)) {
                    return (
                        <TrackRow
                            key={item.id}
                            track={item}
                            onClick={onTrackClick ?? (() => undefined)}
                        />
                    );
                }
                if (isSearchPlaylist(item)) {
                    return (
                        <PlaylistRow
                            key={item.id}
                            playlist={item}
                            onClick={onPlaylistClick ?? (() => undefined)}
                        />
                    );
                }
                if (isSearchAlbum(item)) {
                    return (
                        <div
                            key={item.id}
                            role="button"
                            tabIndex={0}
                            className="flex items-center gap-2 px-2 py-1.5 cursor-pointer hover:bg-[var(--surface-hover)] transition-colors duration-[var(--dur-fast)]"
                            onClick={() => onAlbumClick?.(item)}
                            onKeyDown={(e) => {
                                if (e.key === 'Enter' || e.key === ' ') onAlbumClick?.(item);
                            }}
                        >
                            <span className="flex-shrink-0 w-7 h-7 flex items-center justify-center text-[9px] font-bold text-[var(--accent)] border border-[var(--accent)] font-[var(--font)] tracking-widest">
                                {item.monogram}
                            </span>
                            <div className="flex flex-col min-w-0 flex-1">
                                <span className="text-[11px] text-[var(--text)] font-[var(--font)] truncate">
                                    {item.name}
                                </span>
                                <span className="text-[9px] text-[var(--text-muted)] font-[var(--font)] truncate">
                                    {item.artist}
                                </span>
                            </div>
                        </div>
                    );
                }
                // Narrowed to SpotifyArtist after all other checks
                return (
                    <div
                        key={item.id}
                        role="button"
                        tabIndex={0}
                        className="flex items-center gap-2 px-2 py-1.5 cursor-pointer hover:bg-[var(--surface-hover)] transition-colors duration-[var(--dur-fast)]"
                        onClick={() => onArtistClick?.(item)}
                        onKeyDown={(e) => {
                            if (e.key === 'Enter' || e.key === ' ') onArtistClick?.(item);
                        }}
                    >
                        <span className="flex-shrink-0 w-7 h-7 flex items-center justify-center text-[9px] font-bold text-[var(--accent)] border border-[var(--accent)] font-[var(--font)] tracking-widest">
                            {item.monogram}
                        </span>
                        <span className="text-[11px] text-[var(--text)] font-[var(--font)] truncate flex-1">
                            {item.name}
                        </span>
                    </div>
                );
            })}
        </div>
    );
}

export default ResultGroup;
