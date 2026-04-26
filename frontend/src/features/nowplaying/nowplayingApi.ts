import { baseApi } from '@core/api/baseApi';
import { wsClient } from '@core/websocket/wsClient';
import { spotifyStateReceived } from './nowplayingSlice';
import type {
    SpotifyStatePayload,
    SpotifyCmdAction,
    SpotifyPlaylist,
    SpotifyTrackResult,
    SpotifyAlbum,
    SpotifySearchResults,
    SpotifyQueueItem,
    SpotifyLibraryPage,
} from './types';

export const nowplayingApi = baseApi.injectEndpoints({
    endpoints: (builder) => ({
        streamNowplaying: builder.query<null, void>({
            queryFn: () => ({ data: null }),
            async onCacheEntryAdded(_arg, { cacheDataLoaded, cacheEntryRemoved, dispatch }) {
                await cacheDataLoaded;

                const unsub = wsClient.subscribe<{ type: string; payload: SpotifyStatePayload }>(
                    'spotify_state',
                    (msg) => dispatch(spotifyStateReceived(msg.payload)),
                );

                await cacheEntryRemoved;
                unsub();
            },
        }),

        getPlaylists: builder.query<SpotifyLibraryPage<SpotifyPlaylist>, { limit?: number; offset?: number }>({
            query: ({ limit = 50, offset = 0 } = {}) =>
                `/api/spotify/playlists?limit=${limit}&offset=${offset}`,
        }),

        getPlaylistTracks: builder.query<SpotifyLibraryPage<SpotifyTrackResult>, { id: string; limit?: number; offset?: number }>({
            query: ({ id, limit = 50, offset = 0 }) =>
                `/api/spotify/playlists/${encodeURIComponent(id)}/tracks?limit=${limit}&offset=${offset}`,
        }),

        getAlbumTracks: builder.query<SpotifyLibraryPage<SpotifyTrackResult>, { id: string; limit?: number; offset?: number }>({
            query: ({ id, limit = 50, offset = 0 }) =>
                `/api/spotify/albums/${encodeURIComponent(id)}/tracks?limit=${limit}&offset=${offset}`,
        }),

        getSavedTracks: builder.query<SpotifyLibraryPage<SpotifyTrackResult>, { limit?: number; offset?: number }>({
            query: ({ limit = 50, offset = 0 } = {}) =>
                `/api/spotify/me/tracks?limit=${limit}&offset=${offset}`,
        }),

        getSavedAlbums: builder.query<SpotifyLibraryPage<SpotifyAlbum>, { limit?: number; offset?: number }>({
            query: ({ limit = 50, offset = 0 } = {}) =>
                `/api/spotify/me/albums?limit=${limit}&offset=${offset}`,
        }),

        searchSpotify: builder.query<SpotifySearchResults, { q: string; types?: string }>({
            query: ({ q, types = 'track,artist,album,playlist' }) =>
                `/api/spotify/search?q=${encodeURIComponent(q)}&types=${encodeURIComponent(types)}`,
        }),

        getQueue: builder.query<{ items: SpotifyQueueItem[] }, void>({
            query: () => '/api/spotify/queue',
        }),

        addToQueue: builder.mutation<void, { uri: string }>({
            query: (body) => ({
                url: '/api/spotify/queue',
                method: 'POST',
                body,
            }),
        }),

        playContext: builder.mutation<void, { context_uri: string; offset_uri?: string }>({
            query: (body) => ({
                url: '/api/spotify/play/context',
                method: 'POST',
                body,
            }),
        }),

        playUris: builder.mutation<void, { uris: string[] }>({
            query: (body) => ({
                url: '/api/spotify/play/uris',
                method: 'POST',
                body,
            }),
        }),
    }),
    overrideExisting: false,
});

export const {
    useStreamNowplayingQuery,
    useGetPlaylistsQuery,
    useGetPlaylistTracksQuery,
    useGetAlbumTracksQuery,
    useGetSavedTracksQuery,
    useGetSavedAlbumsQuery,
    useSearchSpotifyQuery,
    useGetQueueQuery,
    useAddToQueueMutation,
    usePlayContextMutation,
    usePlayUrisMutation,
} = nowplayingApi;

/**
 * One-way command helper — sends a Spotify transport command without waiting
 * for a server acknowledgement. No Redux involvement.
 */
export function sendSpotifyCmd(action: SpotifyCmdAction, value?: number): void {
    wsClient.send({ type: 'spotify_cmd', payload: { action, value } });
}
