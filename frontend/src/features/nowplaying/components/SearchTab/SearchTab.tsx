import { useCallback } from 'react';
import type { ReactElement } from 'react';
import { useSpotifyFull } from '../../hooks/useSpotifyFull';
import { SearchInput } from '../SearchInput';
import { ResultGroup } from '../ResultGroup';
import type {
    SpotifyPlaylist,
    SpotifyAlbum,
    SpotifyArtist,
} from '../../types';
import type { SearchTabProps } from './SearchTab.types';

export function SearchTab(_props: SearchTabProps): ReactElement {
    const {
        searchQuery,
        setSearchQuery,
        searchResults,
        isLoadingSearch,
        playUris,
        openPlaylist,
        playContext,
    } = useSpotifyFull();

    const handleSearch = useCallback(
        (q: string): void => {
            setSearchQuery(q);
        },
        [setSearchQuery],
    );

    // Fix #5: onChange is a no-op — onSearch (debounced) is the sole Redux updater.
    // This prevents double-dispatch on every keystroke.
    const handleNoOp = useCallback((_v: string): void => {
        // intentionally empty
    }, []);

    const handleTrackClick = useCallback(
        (uri: string): void => {
            playUris([uri]);
        },
        [playUris],
    );

    const handlePlaylistClick = useCallback(
        (playlist: SpotifyPlaylist): void => {
            openPlaylist(playlist.id, playlist.uri);
        },
        [openPlaylist],
    );

    const handleAlbumClick = useCallback(
        (album: SpotifyAlbum): void => {
            playContext(album.uri);
        },
        [playContext],
    );

    const handleArtistClick = useCallback(
        (artist: SpotifyArtist): void => {
            playContext(artist.uri);
        },
        [playContext],
    );

    const hasQuery = searchQuery.trim().length > 0;

    return (
        <div className="flex flex-col overflow-hidden flex-1">
            {/* onChange is intentionally a no-op: onSearch (debounced) is the sole Redux updater (fix #5). */}
            <SearchInput
                value={searchQuery}
                onChange={handleNoOp}
                onSearch={handleSearch}
            />
            {!hasQuery && (
                <div className="flex items-center justify-center flex-1 text-[10px] text-[var(--text-muted)] font-[var(--font)] tracking-widest">
                    TYPE TO SEARCH
                </div>
            )}
            {hasQuery && isLoadingSearch && (
                <div className="flex items-center justify-center flex-1 text-[10px] text-[var(--text-muted)] font-[var(--font)] tracking-widest">
                    SEARCHING...
                </div>
            )}
            {hasQuery && !isLoadingSearch && searchResults !== undefined && (
                <div className="overflow-y-auto flex-1">
                    <ResultGroup
                        label="TRACKS"
                        items={searchResults.tracks}
                        onTrackClick={handleTrackClick}
                    />
                    <ResultGroup
                        label="ARTISTS"
                        items={searchResults.artists}
                        onArtistClick={handleArtistClick}
                    />
                    <ResultGroup
                        label="ALBUMS"
                        items={searchResults.albums}
                        onAlbumClick={handleAlbumClick}
                    />
                    <ResultGroup
                        label="PLAYLISTS"
                        items={searchResults.playlists}
                        onPlaylistClick={handlePlaylistClick}
                    />
                    {searchResults.tracks.length === 0 &&
                        searchResults.artists.length === 0 &&
                        searchResults.albums.length === 0 &&
                        searchResults.playlists.length === 0 && (
                            <div className="flex items-center justify-center py-4 text-[10px] text-[var(--text-muted)] font-[var(--font)] tracking-widest">
                                NO RESULTS
                            </div>
                        )}
                </div>
            )}
        </div>
    );
}

export default SearchTab;
