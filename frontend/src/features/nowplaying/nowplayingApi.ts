import { baseApi } from '@core/api/baseApi';
import { wsClient } from '@core/websocket/wsClient';
import { spotifyStateReceived } from './nowplayingSlice';
import { deriveMonogram } from './utils';
import type {
    SpotifyStatePayload,
    SpotifyCmdAction,
    SpotifyPlaylist,
    SpotifyTrackResult,
    SpotifyAlbum,
    SpotifyArtist,
    SpotifySearchResults,
    SpotifyQueueItem,
    SpotifyLibraryPage,
} from './types';

// ---------------------------------------------------------------------------
// Raw backend shapes (before monogram is derived)
// ---------------------------------------------------------------------------

interface RawPlaylist {
    id: string;
    name: string;
    owner: string;
    track_count: number;
    uri: string;
}

interface RawTrackResult {
    id: string;
    name: string;
    artist: string;
    album: string;
    duration_ms: number;
    uri: string;
}

interface RawAlbum {
    id: string;
    name: string;
    artist: string;
    uri: string;
    track_count: number;
}

interface RawArtist {
    id: string;
    name: string;
    uri: string;
}

interface RawQueueItem {
    position: number;
    name: string;
    artist: string;
    uri: string;
}

interface RawLibraryPage<T> {
    items: T[];
    total: number;
    offset: number;
}

interface RawSearchResults {
    tracks: RawTrackResult[];
    artists: RawArtist[];
    albums: RawAlbum[];
    playlists: RawPlaylist[];
}

// ---------------------------------------------------------------------------
// Transform helpers
// ---------------------------------------------------------------------------

function transformPlaylist(raw: RawPlaylist): SpotifyPlaylist {
    return {
        id: raw.id,
        name: raw.name,
        owner: raw.owner,
        trackCount: raw.track_count,
        uri: raw.uri,
        monogram: deriveMonogram(raw.name),
    };
}

function transformTrack(raw: RawTrackResult): SpotifyTrackResult {
    return {
        id: raw.id,
        name: raw.name,
        artist: raw.artist,
        album: raw.album,
        durationMs: raw.duration_ms,
        uri: raw.uri,
        monogram: deriveMonogram(raw.name),
    };
}

function transformAlbum(raw: RawAlbum): SpotifyAlbum {
    return {
        id: raw.id,
        name: raw.name,
        artist: raw.artist,
        uri: raw.uri,
        trackCount: raw.track_count,
        monogram: deriveMonogram(raw.name),
    };
}

function transformArtist(raw: RawArtist): SpotifyArtist {
    return {
        id: raw.id,
        name: raw.name,
        uri: raw.uri,
        monogram: deriveMonogram(raw.name),
    };
}

function transformQueueItem(raw: RawQueueItem): SpotifyQueueItem {
    return {
        position: raw.position,
        name: raw.name,
        artist: raw.artist,
        uri: raw.uri,
        monogram: deriveMonogram(raw.name),
    };
}

// ---------------------------------------------------------------------------
// API
// ---------------------------------------------------------------------------

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
            transformResponse: (raw: RawLibraryPage<RawPlaylist>): SpotifyLibraryPage<SpotifyPlaylist> => ({
                items: raw.items.map(transformPlaylist),
                total: raw.total,
                offset: raw.offset,
            }),
        }),

        getPlaylistTracks: builder.query<SpotifyLibraryPage<SpotifyTrackResult>, { id: string; limit?: number; offset?: number }>({
            query: ({ id, limit = 50, offset = 0 }) =>
                `/api/spotify/playlists/${encodeURIComponent(id)}/tracks?limit=${limit}&offset=${offset}`,
            transformResponse: (raw: RawLibraryPage<RawTrackResult>): SpotifyLibraryPage<SpotifyTrackResult> => ({
                items: raw.items.map(transformTrack),
                total: raw.total,
                offset: raw.offset,
            }),
        }),

        getAlbumTracks: builder.query<SpotifyLibraryPage<SpotifyTrackResult>, { id: string; limit?: number; offset?: number }>({
            query: ({ id, limit = 50, offset = 0 }) =>
                `/api/spotify/albums/${encodeURIComponent(id)}/tracks?limit=${limit}&offset=${offset}`,
            transformResponse: (raw: RawLibraryPage<RawTrackResult>): SpotifyLibraryPage<SpotifyTrackResult> => ({
                items: raw.items.map(transformTrack),
                total: raw.total,
                offset: raw.offset,
            }),
        }),

        getSavedTracks: builder.query<SpotifyLibraryPage<SpotifyTrackResult>, { limit?: number; offset?: number }>({
            query: ({ limit = 50, offset = 0 } = {}) =>
                `/api/spotify/me/tracks?limit=${limit}&offset=${offset}`,
            transformResponse: (raw: RawLibraryPage<RawTrackResult>): SpotifyLibraryPage<SpotifyTrackResult> => ({
                items: raw.items.map(transformTrack),
                total: raw.total,
                offset: raw.offset,
            }),
        }),

        getSavedAlbums: builder.query<SpotifyLibraryPage<SpotifyAlbum>, { limit?: number; offset?: number }>({
            query: ({ limit = 50, offset = 0 } = {}) =>
                `/api/spotify/me/albums?limit=${limit}&offset=${offset}`,
            transformResponse: (raw: RawLibraryPage<RawAlbum>): SpotifyLibraryPage<SpotifyAlbum> => ({
                items: raw.items.map(transformAlbum),
                total: raw.total,
                offset: raw.offset,
            }),
        }),

        searchSpotify: builder.query<SpotifySearchResults, { q: string; types?: string }>({
            query: ({ q, types = 'track,artist,album,playlist' }) =>
                `/api/spotify/search?q=${encodeURIComponent(q)}&types=${encodeURIComponent(types)}`,
            transformResponse: (raw: RawSearchResults): SpotifySearchResults => ({
                tracks: raw.tracks.map(transformTrack),
                artists: raw.artists.map(transformArtist),
                albums: raw.albums.map(transformAlbum),
                playlists: raw.playlists.map(transformPlaylist),
            }),
        }),

        getQueue: builder.query<{ items: SpotifyQueueItem[] }, void>({
            query: () => '/api/spotify/queue',
            transformResponse: (raw: { items: RawQueueItem[] }): { items: SpotifyQueueItem[] } => ({
                items: raw.items.map(transformQueueItem),
            }),
            providesTags: ['queue'],
        }),

        addToQueue: builder.mutation<void, { uri: string }>({
            query: (body) => ({
                url: '/api/spotify/queue',
                method: 'POST',
                body,
            }),
            invalidatesTags: ['queue'],
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
