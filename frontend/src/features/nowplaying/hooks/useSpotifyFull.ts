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
    setPremiumError,
} from '../nowplayingSlice';
import {
    selectActiveTab,
    selectLibraryView,
    selectSelectedPlaylistId,
    selectSelectedPlaylistUri,
    selectSelectedAlbumUri,
    selectSearchQuery,
    selectPremiumError,
} from '../nowplayingSelectors';
import {
    useGetPlaylistsQuery,
    useGetPlaylistTracksQuery,
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
    const selectedAlbumUri = useAppSelector(selectSelectedAlbumUri);
    const searchQuery = useAppSelector(selectSearchQuery);
    const premiumError = useAppSelector(selectPremiumError);

    // Single call with the correct page limit — LibraryTab reads data from here
    const { data: playlistsPage, isLoading: isLoadingPlaylists } = useGetPlaylistsQuery(
        { limit: LIBRARY_PAGE_LIMIT },
        { skip: activeTab !== 'library' },
    );

    const { isLoading: isLoadingPlaylistTracks } = useGetPlaylistTracksQuery(
        { id: selectedPlaylistId ?? '', limit: LIBRARY_PAGE_LIMIT },
        { skip: libraryView !== 'playlist-tracks' || selectedPlaylistId === null },
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
            addToQueueMutation({ uri })
                .unwrap()
                .catch(() => {
                    dispatch(setPremiumError(true));
                });
        },
        [addToQueueMutation, dispatch],
    );

    const handlePlayContext = useCallback(
        (contextUri: string, offsetUri?: string): void => {
            playContextMutation({ context_uri: contextUri, offset_uri: offsetUri })
                .unwrap()
                .catch(() => {
                    dispatch(setPremiumError(true));
                });
        },
        [playContextMutation, dispatch],
    );

    const handlePlayUris = useCallback(
        (uris: string[]): void => {
            playUrisMutation({ uris })
                .unwrap()
                .catch(() => {
                    dispatch(setPremiumError(true));
                });
        },
        [playUrisMutation, dispatch],
    );

    const isLoadingLibrary = isLoadingPlaylists || isLoadingPlaylistTracks;

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
    };
}
