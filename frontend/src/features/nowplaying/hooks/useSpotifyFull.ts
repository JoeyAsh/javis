import { useCallback } from 'react';
import { useAppSelector, useAppDispatch } from '@app';
import {
    setActiveTab,
    setLibraryView as setLibraryViewAction,
    selectPlaylist,
    setSelectedPlaylistUri,
    selectAlbum,
    setSelectedAlbumUri,
    setSearchQuery,
} from '../nowplayingSlice';
import {
    selectActiveTab,
    selectLibraryView,
    selectSelectedPlaylistId,
    selectSelectedPlaylistUri,
    selectSelectedAlbumId,
    selectSelectedAlbumUri,
    selectSearchQuery,
    selectPremiumError,
    selectSdkDeviceId,
} from '../nowplayingSelectors';
import {
    useGetPlaylistsQuery,
    useGetPlaylistTracksQuery,
    useGetAlbumTracksQuery,
    useSearchSpotifyQuery,
    useGetQueueQuery,
    useAddToQueueMutation,
    usePlayContextMutation,
    usePlayUrisMutation,
} from '../nowplayingApi';
import { LIBRARY_PAGE_LIMIT } from '../constants';
import type { SpotifyTab, SpotifyPlaylist, SpotifyLibraryPage } from '../types';
import type { UseSpotifyFullReturn } from './useSpotifyFull.types';

export function useSpotifyFull(): UseSpotifyFullReturn {
    const dispatch = useAppDispatch();

    const activeTab = useAppSelector(selectActiveTab);
    const libraryView = useAppSelector(selectLibraryView);
    const selectedPlaylistId = useAppSelector(selectSelectedPlaylistId);
    const selectedPlaylistUri = useAppSelector(selectSelectedPlaylistUri);
    const selectedAlbumId = useAppSelector(selectSelectedAlbumId);
    const selectedAlbumUri = useAppSelector(selectSelectedAlbumUri);
    const searchQuery = useAppSelector(selectSearchQuery);
    const premiumError = useAppSelector(selectPremiumError);
    const sdkDeviceId = useAppSelector(selectSdkDeviceId);

    // Single call with the correct page limit — LibraryTab reads data from here
    const { data: playlistsPage, isLoading: isLoadingPlaylists } = useGetPlaylistsQuery(
        { limit: LIBRARY_PAGE_LIMIT },
        { skip: activeTab !== 'library' },
    );

    const { isLoading: isLoadingPlaylistTracks } = useGetPlaylistTracksQuery(
        { id: selectedPlaylistId ?? '', limit: LIBRARY_PAGE_LIMIT },
        { skip: libraryView !== 'playlist-tracks' || selectedPlaylistId === null },
    );

    const { isLoading: isLoadingAlbumTracks } = useGetAlbumTracksQuery(
        { id: selectedAlbumId ?? '', limit: LIBRARY_PAGE_LIMIT },
        { skip: libraryView !== 'album-tracks' || selectedAlbumId === null },
    );

    const { data: searchResults, isLoading: isLoadingSearch } = useSearchSpotifyQuery(
        { q: searchQuery },
        { skip: searchQuery.trim().length === 0 },
    );

    const { data: queueData, isLoading: isLoadingQueue } = useGetQueueQuery(undefined, {
        skip: activeTab !== 'queue',
    });

    const [addToQueueMutation] = useAddToQueueMutation();
    const [playContextMutation] = usePlayContextMutation();
    const [playUrisMutation] = usePlayUrisMutation();

    const handleSetActiveTab = useCallback(
        (tab: SpotifyTab): void => {
            dispatch(setActiveTab(tab));
        },
        [dispatch],
    );

    // Store both id and uri so LibraryTab can call playContext with the context URI
    const openPlaylist = useCallback(
        (id: string, uri: string): void => {
            dispatch(selectPlaylist(id));
            dispatch(setSelectedPlaylistUri(uri));
            dispatch(setLibraryViewAction('playlist-tracks'));
        },
        [dispatch],
    );

    const openAlbum = useCallback(
        (id: string, uri: string): void => {
            dispatch(selectAlbum(id));
            dispatch(setSelectedAlbumUri(uri));
            dispatch(setLibraryViewAction('album-tracks'));
        },
        [dispatch],
    );

    const goBack = useCallback((): void => {
        dispatch(setLibraryViewAction('playlists'));
        dispatch(selectPlaylist(null));
        dispatch(selectAlbum(null));
    }, [dispatch]);

    const handleSetSearchQuery = useCallback(
        (q: string): void => {
            dispatch(setSearchQuery(q));
        },
        [dispatch],
    );

    const handleAddToQueue = useCallback(
        (uri: string): void => {
            addToQueueMutation({ uri, device_id: sdkDeviceId ?? undefined })
                .unwrap()
                .catch((err: unknown) => {
                    const status =
                        err !== null && typeof err === 'object' && 'status' in err
                            ? (err as { status?: number }).status
                            : undefined;
                    if (status === 402) {
                        // Per-resource 402 (Spotify playlist/track restriction) — do NOT flip the
                        // global premiumError flag. The SDK account_error event is the single
                        // source of truth for "user is not Premium".
                        console.warn('[JARVIS] Spotify add-to-queue denied (402) — resource may be restricted:', err);
                    }
                });
        },
        [addToQueueMutation, sdkDeviceId],
    );

    const handlePlayContext = useCallback(
        (contextUri: string, offsetUri?: string): void => {
            playContextMutation({
                context_uri: contextUri,
                offset_uri: offsetUri,
                device_id: sdkDeviceId ?? undefined,
            })
                .unwrap()
                .catch((err: unknown) => {
                    const status =
                        err !== null && typeof err === 'object' && 'status' in err
                            ? (err as { status?: number }).status
                            : undefined;
                    if (status === 402) {
                        // Per-resource 402 — do NOT flip premiumError. The user IS premium;
                        // this particular context URI is restricted by Spotify.
                        console.warn('[JARVIS] Spotify play-context denied (402) — resource may be restricted:', err);
                    }
                });
        },
        [playContextMutation, sdkDeviceId],
    );

    const handlePlayUris = useCallback(
        (uris: string[]): void => {
            playUrisMutation({ uris, device_id: sdkDeviceId ?? undefined })
                .unwrap()
                .catch((err: unknown) => {
                    const status =
                        err !== null && typeof err === 'object' && 'status' in err
                            ? (err as { status?: number }).status
                            : undefined;
                    if (status === 402) {
                        // Per-resource 402 — do NOT flip premiumError.
                        console.warn('[JARVIS] Spotify play-uris denied (402) — resource may be restricted:', err);
                    }
                });
        },
        [playUrisMutation, sdkDeviceId],
    );

    const isLoadingLibrary = isLoadingPlaylists || isLoadingPlaylistTracks || isLoadingAlbumTracks;

    return {
        activeTab,
        setActiveTab: handleSetActiveTab,

        libraryView,
        openPlaylist,
        openAlbum,
        goBack,

        playlistsPage: playlistsPage as SpotifyLibraryPage<SpotifyPlaylist> | undefined,
        selectedPlaylistUri,
        selectedAlbumUri,

        searchQuery,
        setSearchQuery: handleSetSearchQuery,
        searchResults,
        isLoadingSearch,

        queue: queueData?.items ?? [],
        isLoadingQueue,

        addToQueue: handleAddToQueue,
        playContext: handlePlayContext,
        playUris: handlePlayUris,

        premiumError,
        isLoadingLibrary,
        isLoadingPlaylistTracks,
        isLoadingAlbumTracks,
    };
}
