import { useCallback } from 'react';
import type { ReactElement } from 'react';
import { useSpotifyFull } from '../../hooks/useSpotifyFull';
import { useGetPlaylistTracksQuery, useGetAlbumTracksQuery } from '../../nowplayingApi';
import { useAppSelector } from '@app';
import {
    selectSelectedPlaylistId,
    selectSelectedAlbumId,
    selectLibraryView,
} from '../../nowplayingSelectors';
import { LIBRARY_PAGE_LIMIT } from '../../constants';
import { PlaylistRow } from '../PlaylistRow';
import { TrackRow } from '../TrackRow';
import type { SpotifyPlaylist, SpotifyTrackResult } from '../../types';
import type { LibraryTabProps } from './LibraryTab.types';

export function LibraryTab(_props: LibraryTabProps): ReactElement {
    const {
        openPlaylist,
        goBack,
        playContext,
        playUris,
        addToQueue,
        premiumError,
        isLoadingLibrary,
        isLoadingPlaylistTracks,
        isLoadingAlbumTracks,
        playlistsPage,
        selectedPlaylistUri,
        selectedAlbumUri,
    } = useSpotifyFull();

    const libraryView = useAppSelector(selectLibraryView);
    const selectedPlaylistId = useAppSelector(selectSelectedPlaylistId);
    const selectedAlbumId = useAppSelector(selectSelectedAlbumId);

    const { data: tracksPage } = useGetPlaylistTracksQuery(
        { id: selectedPlaylistId ?? '', limit: LIBRARY_PAGE_LIMIT },
        { skip: libraryView !== 'playlist-tracks' || selectedPlaylistId === null },
    );

    const { data: albumTracksPage } = useGetAlbumTracksQuery(
        { id: selectedAlbumId ?? '', limit: LIBRARY_PAGE_LIMIT },
        { skip: libraryView !== 'album-tracks' || selectedAlbumId === null },
    );

    const handlePlaylistClick = useCallback(
        (playlist: SpotifyPlaylist): void => {
            openPlaylist(playlist.id, playlist.uri);
        },
        [openPlaylist],
    );

    // use playContext so playback joins the correct queue context.
    // playlist-tracks and album-tracks both supply a context URI;
    // saved-tracks (no parent context) falls back to playUris.
    const handleTrackClick = useCallback(
        (uri: string): void => {
            if (libraryView === 'playlist-tracks' && selectedPlaylistUri !== null) {
                playContext(selectedPlaylistUri, uri);
            } else if (libraryView === 'album-tracks' && selectedAlbumUri !== null) {
                playContext(selectedAlbumUri, uri);
            } else {
                playUris([uri]);
            }
        },
        [libraryView, selectedPlaylistUri, selectedAlbumUri, playContext, playUris],
    );

    if (premiumError) {
        return (
            <div className="flex items-center justify-center py-4 text-[10px] text-[var(--text-muted)] font-[var(--font)] tracking-wide">
                SPOTIFY PREMIUM REQUIRED
            </div>
        );
    }

    if (isLoadingLibrary) {
        return (
            <div className="flex items-center justify-center py-4 text-[10px] text-[var(--text-muted)] font-[var(--font)] tracking-wide">
                LOADING...
            </div>
        );
    }

    // Always enter this branch when libraryView === 'playlist-tracks' so a click on a playlist
    // is never silently ignored. When tracksPage is undefined we show an appropriate sub-state.
    if (libraryView === 'playlist-tracks') {
        const selectedName =
            playlistsPage?.items.find((p: SpotifyPlaylist) => p.id === selectedPlaylistId)?.name ??
            'PLAYLIST';

        const backButton = (
            <div className="flex items-center gap-2 mb-2 px-2 flex-shrink-0">
                <button
                    type="button"
                    aria-label="Back to playlists"
                    className="text-[9px] text-[var(--accent)] font-[var(--font)] tracking-widest hover:text-[var(--accent-bright)] transition-colors duration-[var(--dur-fast)] cursor-pointer bg-transparent border-none p-0"
                    onClick={goBack}
                >
                    ← BACK
                </button>
                <span className="text-[9px] text-[var(--text-muted)] font-[var(--font)] tracking-widest truncate">
                    {selectedName.toUpperCase()}
                </span>
            </div>
        );

        if (tracksPage === undefined && isLoadingPlaylistTracks) {
            return (
                <div className="flex flex-col overflow-hidden flex-1">
                    {backButton}
                    <div className="flex items-center justify-center py-4 text-[10px] text-[var(--text-muted)] font-[var(--font)] tracking-wide">
                        LOADING...
                    </div>
                </div>
            );
        }

        if (tracksPage === undefined) {
            return (
                <div className="flex flex-col overflow-hidden flex-1">
                    {backButton}
                    <div className="flex items-center justify-center py-4 text-[10px] text-[var(--text-muted)] font-[var(--font)] tracking-wide">
                        PLAYLIST NICHT VERFÜGBAR
                    </div>
                </div>
            );
        }

        return (
            <div className="flex flex-col overflow-hidden flex-1">
                {backButton}
                <div className="overflow-y-auto flex-1">
                    {tracksPage.items.map((track: SpotifyTrackResult, idx: number) => (
                        <TrackRow
                            key={track.id}
                            track={track}
                            index={idx}
                            onClick={handleTrackClick}
                            onAddToQueue={addToQueue}
                        />
                    ))}
                    {tracksPage.offset + tracksPage.items.length < tracksPage.total && (
                        <div className="px-2 py-2 text-[9px] text-[var(--text-muted)] font-[var(--font)] tracking-widest text-center">
                            + {tracksPage.total - tracksPage.offset - tracksPage.items.length} MORE
                        </div>
                    )}
                </div>
            </div>
        );
    }

    // Always enter this branch when libraryView === 'album-tracks'.
    if (libraryView === 'album-tracks') {
        const backButton = (
            <div className="flex items-center gap-2 mb-2 px-2 flex-shrink-0">
                <button
                    type="button"
                    aria-label="Back to playlists"
                    className="text-[9px] text-[var(--accent)] font-[var(--font)] tracking-widest hover:text-[var(--accent-bright)] transition-colors duration-[var(--dur-fast)] cursor-pointer bg-transparent border-none p-0"
                    onClick={goBack}
                >
                    ← BACK
                </button>
                <span className="text-[9px] text-[var(--text-muted)] font-[var(--font)] tracking-widest truncate">
                    ALBUM
                </span>
            </div>
        );

        if (albumTracksPage === undefined && isLoadingAlbumTracks) {
            return (
                <div className="flex flex-col overflow-hidden flex-1">
                    {backButton}
                    <div className="flex items-center justify-center py-4 text-[10px] text-[var(--text-muted)] font-[var(--font)] tracking-wide">
                        LOADING...
                    </div>
                </div>
            );
        }

        if (albumTracksPage === undefined) {
            return (
                <div className="flex flex-col overflow-hidden flex-1">
                    {backButton}
                    <div className="flex items-center justify-center py-4 text-[10px] text-[var(--text-muted)] font-[var(--font)] tracking-wide">
                        PLAYLIST NICHT VERFÜGBAR
                    </div>
                </div>
            );
        }

        return (
            <div className="flex flex-col overflow-hidden flex-1">
                {backButton}
                <div className="overflow-y-auto flex-1">
                    {albumTracksPage.items.map((track: SpotifyTrackResult, idx: number) => (
                        <TrackRow
                            key={track.id}
                            track={track}
                            index={idx}
                            onClick={handleTrackClick}
                            onAddToQueue={addToQueue}
                        />
                    ))}
                    {albumTracksPage.offset + albumTracksPage.items.length < albumTracksPage.total && (
                        <div className="px-2 py-2 text-[9px] text-[var(--text-muted)] font-[var(--font)] tracking-widest text-center">
                            + {albumTracksPage.total - albumTracksPage.offset - albumTracksPage.items.length} MORE
                        </div>
                    )}
                </div>
            </div>
        );
    }

    if (playlistsPage === undefined) {
        return (
            <div className="flex items-center justify-center py-4 text-[10px] text-[var(--text-muted)] font-[var(--font)] tracking-wide">
                LOADING...
            </div>
        );
    }

    return (
        <div className="overflow-y-auto flex-1">
            {playlistsPage.items.map((playlist: SpotifyPlaylist) => (
                <PlaylistRow
                    key={playlist.id}
                    playlist={playlist}
                    onClick={handlePlaylistClick}
                />
            ))}
            {playlistsPage.offset + playlistsPage.items.length < playlistsPage.total && (
                <div className="px-2 py-2 text-[9px] text-[var(--text-muted)] font-[var(--font)] tracking-widest text-center">
                    + {playlistsPage.total - playlistsPage.offset - playlistsPage.items.length} MORE
                </div>
            )}
        </div>
    );
}

export default LibraryTab;
