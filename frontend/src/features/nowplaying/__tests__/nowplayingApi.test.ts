/**
 * nowplayingApi — RTK Query endpoint tests (issue #58 new endpoints).
 *
 * Verifies URL shapes, query-param serialisation, and transformResponse output
 * for all 10 new endpoints, plus streamNowplaying teardown behaviour.
 *
 * Implementation note — why we patch global.Request:
 * RTK Query's fetchBaseQuery calls `new Request(url, opts)` internally before
 * ever reaching `fetch()`. In Node.js (undici) the Request constructor requires
 * an absolute URL; relative paths like "/api/spotify/..." throw "Invalid URL".
 * Patching the Request constructor to normalise relative URLs to
 * `http://localhost<path>` lets the real RTK Query machinery run while our
 * fetch spy captures the resulting absolute URL string.
 *
 * NOTE on getQueue freshness: getQueue uses the default RTK Query caching
 * (no refetchOnMountOrArgChange). For live-queue UX this may result in
 * stale data if the cache isn't manually invalidated. Consider adding
 * `refetchOnMountOrArgChange: true` to the getQueue endpoint definition
 * if queue freshness becomes a concern.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { configureStore } from '@reduxjs/toolkit';
import { baseApi } from '@core/api/baseApi';

// ---------------------------------------------------------------------------
// Mock wsClient singleton — hoisted before any module import.
// This allows streamNowplaying tests to capture subscribe callbacks without
// opening a real WebSocket connection.
// ---------------------------------------------------------------------------

let mockSubscribeCallback: ((msg: unknown) => void) | null = null;
const mockUnsub = vi.fn();

vi.mock('@core/websocket/wsClient', () => ({
    wsClient: {
        subscribe: vi.fn((_type: string, cb: (msg: unknown) => void) => {
            mockSubscribeCallback = cb;
            return mockUnsub;
        }),
        send: vi.fn(),
        connect: vi.fn(),
        disconnect: vi.fn(),
        sendBinary: vi.fn(),
        onStateChange: vi.fn(() => vi.fn()),
        getState: vi.fn(() => 'closed'),
    },
}));

// ---------------------------------------------------------------------------
// Polyfill: allow relative URLs in the Node.js Request constructor.
//
// RTK Query constructs `new Request(url, config)` before calling fetch.
// Node (undici) rejects relative URLs. We wrap the constructor so that any
// relative URL is resolved against http://localhost, matching the jsdom origin.
// ---------------------------------------------------------------------------

const OriginalRequest = global.Request;

class AbsoluteRequest extends OriginalRequest {
    constructor(input: RequestInfo | URL, init?: RequestInit) {
        const url =
            typeof input === 'string' && input.startsWith('/')
                ? `http://localhost${input}`
                : input;
        super(url as RequestInfo | URL, init);
    }
}

beforeEach(() => {
    // @ts-expect-error patching global
    global.Request = AbsoluteRequest;
    vi.restoreAllMocks();
    mockSubscribeCallback = null;
    mockUnsub.mockReset();
});

afterEach(() => {
    global.Request = OriginalRequest;
    vi.useRealTimers();
});

// ---------------------------------------------------------------------------
// Imports used only by the new test groups (transformResponse + streaming).
// Placed after the vi.mock() call so the mock is active when the module tree
// is evaluated.
// ---------------------------------------------------------------------------

import nowplayingReducer from '../nowplayingSlice';
import { deriveMonogram } from '../utils';

// ---------------------------------------------------------------------------
// Minimal store setup — fresh per test to avoid RTK Query cache hits.
// ---------------------------------------------------------------------------

function makeStore() {
    return configureStore({
        reducer: { [baseApi.reducerPath]: baseApi.reducer },
        middleware: (gdm) => gdm().concat(baseApi.middleware),
    });
}

/** Store that also mounts the nowplaying slice (needed for streamNowplaying). */
function makeFullStore() {
    return configureStore({
        reducer: {
            [baseApi.reducerPath]: baseApi.reducer,
            nowplaying: nowplayingReducer,
        },
        middleware: (gdm) => gdm().concat(baseApi.middleware),
    });
}

// Mock fetch to return a minimal valid response.
function mockFetch(body: unknown = {}, status = 200) {
    return vi.spyOn(global, 'fetch').mockResolvedValue(
        new Response(JSON.stringify(body), {
            status,
            headers: { 'Content-Type': 'application/json' },
        }),
    );
}

// ---------------------------------------------------------------------------
// getPlaylists
// ---------------------------------------------------------------------------

describe('getPlaylists', () => {
    it('fetches /api/spotify/playlists with default limit=50&offset=0', async () => {
        const fetchSpy = mockFetch({ items: [], total: 0, offset: 0 });
        const store = makeStore();
        const { nowplayingApi } = await import('../nowplayingApi');

        store.dispatch(nowplayingApi.endpoints.getPlaylists.initiate({}));
        await new Promise((r) => setTimeout(r, 0));

        expect(fetchSpy).toHaveBeenCalled();
        const url = (fetchSpy.mock.calls[0]?.[0] as Request)?.url ?? '';
        expect(url).toContain('/api/spotify/playlists');
        expect(url).toContain('limit=50');
        expect(url).toContain('offset=0');
    });

    it('serialises custom limit and offset', async () => {
        const fetchSpy = mockFetch({ items: [], total: 0, offset: 50 });
        const store = makeStore();
        const { nowplayingApi } = await import('../nowplayingApi');

        store.dispatch(nowplayingApi.endpoints.getPlaylists.initiate({ limit: 25, offset: 50 }));
        await new Promise((r) => setTimeout(r, 0));

        expect(fetchSpy).toHaveBeenCalled();
        const url = (fetchSpy.mock.calls[0]?.[0] as Request)?.url ?? '';
        expect(url).toContain('limit=25');
        expect(url).toContain('offset=50');
    });
});

// ---------------------------------------------------------------------------
// getPlaylistTracks
// ---------------------------------------------------------------------------

describe('getPlaylistTracks', () => {
    it('fetches /api/spotify/playlists/{id}/tracks with encoded ID', async () => {
        const fetchSpy = mockFetch({ items: [], total: 0, offset: 0 });
        const store = makeStore();
        const { nowplayingApi } = await import('../nowplayingApi');

        store.dispatch(nowplayingApi.endpoints.getPlaylistTracks.initiate({ id: 'pl-1', limit: 50, offset: 0 }));
        await new Promise((r) => setTimeout(r, 0));

        expect(fetchSpy).toHaveBeenCalled();
        const url = (fetchSpy.mock.calls[0]?.[0] as Request)?.url ?? '';
        expect(url).toContain('/api/spotify/playlists/');
        expect(url).toContain('pl-1');
        expect(url).toContain('/tracks');
    });
});

// ---------------------------------------------------------------------------
// getAlbumTracks
// ---------------------------------------------------------------------------

describe('getAlbumTracks', () => {
    it('fetches /api/spotify/albums/{id}/tracks', async () => {
        const fetchSpy = mockFetch({ items: [], total: 0, offset: 0 });
        const store = makeStore();
        const { nowplayingApi } = await import('../nowplayingApi');

        store.dispatch(nowplayingApi.endpoints.getAlbumTracks.initiate({ id: 'al-1' }));
        await new Promise((r) => setTimeout(r, 0));

        expect(fetchSpy).toHaveBeenCalled();
        const url = (fetchSpy.mock.calls[0]?.[0] as Request)?.url ?? '';
        expect(url).toContain('/api/spotify/albums/');
        expect(url).toContain('al-1');
        expect(url).toContain('/tracks');
    });
});

// ---------------------------------------------------------------------------
// getSavedTracks
// ---------------------------------------------------------------------------

describe('getSavedTracks', () => {
    it('fetches /api/spotify/me/tracks', async () => {
        const fetchSpy = mockFetch({ items: [], total: 0, offset: 0 });
        const store = makeStore();
        const { nowplayingApi } = await import('../nowplayingApi');

        store.dispatch(nowplayingApi.endpoints.getSavedTracks.initiate({}));
        await new Promise((r) => setTimeout(r, 0));

        expect(fetchSpy).toHaveBeenCalled();
        const url = (fetchSpy.mock.calls[0]?.[0] as Request)?.url ?? '';
        expect(url).toContain('/api/spotify/me/tracks');
    });
});

// ---------------------------------------------------------------------------
// getSavedAlbums
// ---------------------------------------------------------------------------

describe('getSavedAlbums', () => {
    it('fetches /api/spotify/me/albums', async () => {
        const fetchSpy = mockFetch({ items: [], total: 0, offset: 0 });
        const store = makeStore();
        const { nowplayingApi } = await import('../nowplayingApi');

        store.dispatch(nowplayingApi.endpoints.getSavedAlbums.initiate({}));
        await new Promise((r) => setTimeout(r, 0));

        expect(fetchSpy).toHaveBeenCalled();
        const url = (fetchSpy.mock.calls[0]?.[0] as Request)?.url ?? '';
        expect(url).toContain('/api/spotify/me/albums');
    });
});

// ---------------------------------------------------------------------------
// searchSpotify
// ---------------------------------------------------------------------------

describe('searchSpotify', () => {
    it('fetches /api/spotify/search?q=encoded+query', async () => {
        const fetchSpy = mockFetch({ tracks: [], artists: [], albums: [], playlists: [] });
        const store = makeStore();
        const { nowplayingApi } = await import('../nowplayingApi');

        store.dispatch(nowplayingApi.endpoints.searchSpotify.initiate({ q: 'Midnight City' }));
        await new Promise((r) => setTimeout(r, 0));

        expect(fetchSpy).toHaveBeenCalled();
        const url = (fetchSpy.mock.calls[0]?.[0] as Request)?.url ?? '';
        expect(url).toContain('/api/spotify/search');
        expect(url).toContain('Midnight');
    });

    it('serialises types param', async () => {
        const fetchSpy = mockFetch({ tracks: [], artists: [], albums: [], playlists: [] });
        const store = makeStore();
        const { nowplayingApi } = await import('../nowplayingApi');

        store.dispatch(
            nowplayingApi.endpoints.searchSpotify.initiate({
                q: 'test',
                types: 'track,artist',
            }),
        );
        await new Promise((r) => setTimeout(r, 0));

        expect(fetchSpy).toHaveBeenCalled();
        const url = (fetchSpy.mock.calls[0]?.[0] as Request)?.url ?? '';
        expect(url).toContain('types=');
        expect(url).toContain('track');
    });

    it('uses default types when not specified', async () => {
        const fetchSpy = mockFetch({ tracks: [], artists: [], albums: [], playlists: [] });
        const store = makeStore();
        const { nowplayingApi } = await import('../nowplayingApi');

        store.dispatch(nowplayingApi.endpoints.searchSpotify.initiate({ q: 'test' }));
        await new Promise((r) => setTimeout(r, 0));

        expect(fetchSpy).toHaveBeenCalled();
        const url = (fetchSpy.mock.calls[0]?.[0] as Request)?.url ?? '';
        // Default types param should be in the URL
        expect(url).toContain('types=');
    });
});

// ---------------------------------------------------------------------------
// getQueue
// ---------------------------------------------------------------------------

describe('getQueue', () => {
    it('fetches /api/spotify/queue', async () => {
        const fetchSpy = mockFetch({ items: [], total: 0, offset: 0 });
        const store = makeStore();
        const { nowplayingApi } = await import('../nowplayingApi');

        store.dispatch(nowplayingApi.endpoints.getQueue.initiate());
        await new Promise((r) => setTimeout(r, 0));

        expect(fetchSpy).toHaveBeenCalled();
        const url = (fetchSpy.mock.calls[0]?.[0] as Request)?.url ?? '';
        expect(url).toContain('/api/spotify/queue');
    });
});

// ---------------------------------------------------------------------------
// addToQueue (mutation)
// ---------------------------------------------------------------------------

describe('addToQueue', () => {
    it('POSTs to /api/spotify/queue with uri body', async () => {
        const fetchSpy = mockFetch({});
        const store = makeStore();
        const { nowplayingApi } = await import('../nowplayingApi');

        store.dispatch(
            nowplayingApi.endpoints.addToQueue.initiate({ uri: 'spotify:track:t1' }),
        );
        await new Promise((r) => setTimeout(r, 0));

        expect(fetchSpy).toHaveBeenCalled();
        const req = fetchSpy.mock.calls[0]?.[0] as Request;
        expect(req?.url ?? '').toContain('/api/spotify/queue');
        expect(req?.method?.toUpperCase()).toBe('POST');
    });
});

// ---------------------------------------------------------------------------
// playContext (mutation)
// ---------------------------------------------------------------------------

describe('playContext', () => {
    it('POSTs to /api/spotify/play/context', async () => {
        const fetchSpy = mockFetch({});
        const store = makeStore();
        const { nowplayingApi } = await import('../nowplayingApi');

        store.dispatch(
            nowplayingApi.endpoints.playContext.initiate({ context_uri: 'spotify:playlist:pl1' }),
        );
        await new Promise((r) => setTimeout(r, 0));

        expect(fetchSpy).toHaveBeenCalled();
        const req = fetchSpy.mock.calls[0]?.[0] as Request;
        expect(req?.url ?? '').toContain('/api/spotify/play/context');
        expect(req?.method?.toUpperCase()).toBe('POST');
    });
});

// ---------------------------------------------------------------------------
// playUris (mutation)
// ---------------------------------------------------------------------------

describe('playUris', () => {
    it('POSTs to /api/spotify/play/uris', async () => {
        const fetchSpy = mockFetch({});
        const store = makeStore();
        const { nowplayingApi } = await import('../nowplayingApi');

        store.dispatch(
            nowplayingApi.endpoints.playUris.initiate({ uris: ['spotify:track:t1'] }),
        );
        await new Promise((r) => setTimeout(r, 0));

        expect(fetchSpy).toHaveBeenCalled();
        const req = fetchSpy.mock.calls[0]?.[0] as Request;
        expect(req?.url ?? '').toContain('/api/spotify/play/uris');
        expect(req?.method?.toUpperCase()).toBe('POST');
    });
});

// ===========================================================================
// transformResponse output assertions
// ===========================================================================

// ---------------------------------------------------------------------------
// getPlaylists — transformResponse maps RawPlaylist → SpotifyPlaylist
// ---------------------------------------------------------------------------

describe('getPlaylists — transformResponse output', () => {
    it('maps raw camelCase backend payload to SpotifyPlaylist with derived monogram', async () => {
        const rawPlaylist = {
            id: 'pl-abc',
            name: 'Chill Vibes',
            owner: 'johndoe',
            trackCount: 42,
            uri: 'spotify:playlist:pl-abc',
        };
        mockFetch({ items: [rawPlaylist], total: 1, offset: 0 });
        const store = makeStore();
        const { nowplayingApi } = await import('../nowplayingApi');

        const result = await store.dispatch(
            nowplayingApi.endpoints.getPlaylists.initiate({}),
        );

        expect(result.status).toBe('fulfilled');
        const data = (result as { data: { items: unknown[]; total: number; offset: number } }).data;
        expect(data.total).toBe(1);
        expect(data.offset).toBe(0);
        expect(data.items).toHaveLength(1);

        const playlist = data.items[0] as {
            id: string;
            name: string;
            owner: string;
            trackCount: number;
            uri: string;
            monogram: string;
        };
        // Camelcase fields present
        expect(playlist.trackCount).toBe(42);
        expect(playlist.uri).toBe('spotify:playlist:pl-abc');
        expect(playlist.owner).toBe('johndoe');
        // monogram is derived from name
        expect(playlist.monogram).toBe(deriveMonogram('Chill Vibes'));
        expect(playlist.monogram).toBe('CHI');
    });

    it('pads monogram with middle-dots when name has fewer than 3 alphanumeric chars', async () => {
        const rawPlaylist = {
            id: 'pl-short',
            name: 'RÄ',  // after stripping non-alphanumeric → 'R', length 1
            owner: 'x',
            trackCount: 1,
            uri: 'spotify:playlist:pl-short',
        };
        mockFetch({ items: [rawPlaylist], total: 1, offset: 0 });
        const store = makeStore();
        const { nowplayingApi } = await import('../nowplayingApi');

        const result = await store.dispatch(
            nowplayingApi.endpoints.getPlaylists.initiate({}),
        );

        const data = (result as { data: { items: unknown[] } }).data;
        const playlist = data.items[0] as { monogram: string };
        expect(playlist.monogram).toBe(deriveMonogram('RÄ'));
        expect(playlist.monogram).toHaveLength(3);
        expect(playlist.monogram).toMatch(/·/);
    });

    it('maps a page with multiple playlists and preserves pagination metadata', async () => {
        const rawItems = [
            { id: 'p1', name: 'Playlist One', owner: 'u1', trackCount: 10, uri: 'spotify:playlist:p1' },
            { id: 'p2', name: 'Playlist Two', owner: 'u2', trackCount: 20, uri: 'spotify:playlist:p2' },
        ];
        mockFetch({ items: rawItems, total: 100, offset: 50 });
        const store = makeStore();
        const { nowplayingApi } = await import('../nowplayingApi');

        const result = await store.dispatch(
            nowplayingApi.endpoints.getPlaylists.initiate({ limit: 2, offset: 50 }),
        );

        const data = (result as { data: { items: unknown[]; total: number; offset: number } }).data;
        expect(data.total).toBe(100);
        expect(data.offset).toBe(50);
        expect(data.items).toHaveLength(2);
        const [first, second] = data.items as Array<{ monogram: string; trackCount: number }>;
        expect(first.monogram).toBe(deriveMonogram('Playlist One'));
        expect(second.trackCount).toBe(20);
    });
});

// ---------------------------------------------------------------------------
// getPlaylistTracks — transformResponse maps RawTrackResult → SpotifyTrackResult
// ---------------------------------------------------------------------------

describe('getPlaylistTracks — transformResponse output', () => {
    it('maps raw track fields to SpotifyTrackResult including durationMs and monogram', async () => {
        const rawTrack = {
            id: 'tr-001',
            name: 'Midnight City',
            artist: 'M83',
            album: 'Hurry Up, We\'re Dreaming',
            durationMs: 243573,
            uri: 'spotify:track:tr-001',
        };
        mockFetch({ items: [rawTrack], total: 1, offset: 0 });
        const store = makeStore();
        const { nowplayingApi } = await import('../nowplayingApi');

        const result = await store.dispatch(
            nowplayingApi.endpoints.getPlaylistTracks.initiate({ id: 'pl-1', limit: 50, offset: 0 }),
        );

        expect(result.status).toBe('fulfilled');
        const data = (result as { data: { items: unknown[] } }).data;
        expect(data.items).toHaveLength(1);

        const track = data.items[0] as {
            id: string;
            name: string;
            artist: string;
            album: string;
            durationMs: number;
            uri: string;
            monogram: string;
        };
        expect(track.durationMs).toBe(243573);
        expect(track.artist).toBe('M83');
        expect(track.uri).toBe('spotify:track:tr-001');
        // monogram derives from track name, not artist
        expect(track.monogram).toBe(deriveMonogram('Midnight City'));
        expect(track.monogram).toBe('MID');
    });

    it('maps multiple tracks and all derive correct monograms', async () => {
        const rawItems = [
            { id: 't1', name: 'Song Alpha', artist: 'Artist A', album: 'Album A', durationMs: 100000, uri: 'spotify:track:t1' },
            { id: 't2', name: 'Song Beta',  artist: 'Artist B', album: 'Album B', durationMs: 200000, uri: 'spotify:track:t2' },
            { id: 't3', name: 'Song Gamma', artist: 'Artist C', album: 'Album C', durationMs: 300000, uri: 'spotify:track:t3' },
        ];
        mockFetch({ items: rawItems, total: 3, offset: 0 });
        const store = makeStore();
        const { nowplayingApi } = await import('../nowplayingApi');

        const result = await store.dispatch(
            nowplayingApi.endpoints.getPlaylistTracks.initiate({ id: 'pl-multi' }),
        );

        const data = (result as { data: { items: unknown[] } }).data;
        expect(data.items).toHaveLength(3);
        const tracks = data.items as Array<{ name: string; monogram: string; durationMs: number }>;
        tracks.forEach((t) => {
            expect(t.monogram).toBe(deriveMonogram(t.name));
        });
        expect(tracks[2].durationMs).toBe(300000);
    });
});

// ---------------------------------------------------------------------------
// searchSpotify — transformResponse maps RawSearchResults → SpotifySearchResults
// ---------------------------------------------------------------------------

describe('searchSpotify — transformResponse output', () => {
    it('maps all four result groups with correct fields and monograms', async () => {
        const rawPayload = {
            tracks: [
                { id: 'tr1', name: 'Track Alpha', artist: 'ArtA', album: 'AlbA', durationMs: 180000, uri: 'spotify:track:tr1' },
            ],
            artists: [
                { id: 'ar1', name: 'Artist One', uri: 'spotify:artist:ar1' },
            ],
            albums: [
                { id: 'al1', name: 'Album One', artist: 'ArtA', uri: 'spotify:album:al1', trackCount: 12 },
            ],
            playlists: [
                { id: 'pl1', name: 'Playlist One', owner: 'joe', trackCount: 30, uri: 'spotify:playlist:pl1' },
            ],
        };
        mockFetch(rawPayload);
        const store = makeStore();
        const { nowplayingApi } = await import('../nowplayingApi');

        const result = await store.dispatch(
            nowplayingApi.endpoints.searchSpotify.initiate({ q: 'Alpha' }),
        );

        expect(result.status).toBe('fulfilled');
        const data = (result as {
            data: {
                tracks: Array<{ durationMs: number; monogram: string }>;
                artists: Array<{ monogram: string; uri: string }>;
                albums: Array<{ trackCount: number; monogram: string }>;
                playlists: Array<{ trackCount: number; owner: string; monogram: string }>;
            };
        }).data;

        // tracks: durationMs preserved, monogram from track name
        expect(data.tracks).toHaveLength(1);
        expect(data.tracks[0].durationMs).toBe(180000);
        expect(data.tracks[0].monogram).toBe(deriveMonogram('Track Alpha'));

        // artists: uri preserved, monogram from name
        expect(data.artists).toHaveLength(1);
        expect(data.artists[0].uri).toBe('spotify:artist:ar1');
        expect(data.artists[0].monogram).toBe(deriveMonogram('Artist One'));

        // albums: trackCount preserved, monogram from album name
        expect(data.albums).toHaveLength(1);
        expect(data.albums[0].trackCount).toBe(12);
        expect(data.albums[0].monogram).toBe(deriveMonogram('Album One'));

        // playlists: trackCount + owner preserved, monogram from playlist name
        expect(data.playlists).toHaveLength(1);
        expect(data.playlists[0].trackCount).toBe(30);
        expect(data.playlists[0].owner).toBe('joe');
        expect(data.playlists[0].monogram).toBe(deriveMonogram('Playlist One'));
    });

    it('returns empty arrays for groups with no results', async () => {
        mockFetch({ tracks: [], artists: [], albums: [], playlists: [] });
        const store = makeStore();
        const { nowplayingApi } = await import('../nowplayingApi');

        const result = await store.dispatch(
            nowplayingApi.endpoints.searchSpotify.initiate({ q: 'zzzzz' }),
        );

        const data = (result as { data: { tracks: unknown[]; artists: unknown[]; albums: unknown[]; playlists: unknown[] } }).data;
        expect(data.tracks).toHaveLength(0);
        expect(data.artists).toHaveLength(0);
        expect(data.albums).toHaveLength(0);
        expect(data.playlists).toHaveLength(0);
    });
});

// ---------------------------------------------------------------------------
// getQueue — transformResponse maps RawQueueItem → SpotifyQueueItem
// ---------------------------------------------------------------------------

describe('getQueue — transformResponse output', () => {
    it('maps queue items preserving position, artist, uri, and deriving monogram', async () => {
        const rawItems = [
            { position: 0, name: 'First Song',  artist: 'Band A', uri: 'spotify:track:q1' },
            { position: 1, name: 'Second Song', artist: 'Band B', uri: 'spotify:track:q2' },
            { position: 2, name: 'Third Song',  artist: 'Band C', uri: 'spotify:track:q3' },
        ];
        mockFetch({ items: rawItems });
        const store = makeStore();
        const { nowplayingApi } = await import('../nowplayingApi');

        const result = await store.dispatch(
            nowplayingApi.endpoints.getQueue.initiate(),
        );

        expect(result.status).toBe('fulfilled');
        const data = (result as { data: { items: Array<{ position: number; name: string; artist: string; uri: string; monogram: string }> } }).data;
        expect(data.items).toHaveLength(3);

        const [first, second, third] = data.items;

        expect(first.position).toBe(0);
        expect(first.artist).toBe('Band A');
        expect(first.uri).toBe('spotify:track:q1');
        expect(first.monogram).toBe(deriveMonogram('First Song'));
        expect(first.monogram).toBe('FIR');

        expect(second.position).toBe(1);
        expect(second.monogram).toBe(deriveMonogram('Second Song'));

        expect(third.position).toBe(2);
        expect(third.monogram).toBe(deriveMonogram('Third Song'));
    });

    it('returns empty items array when queue is empty', async () => {
        mockFetch({ items: [] });
        const store = makeStore();
        const { nowplayingApi } = await import('../nowplayingApi');

        const result = await store.dispatch(
            nowplayingApi.endpoints.getQueue.initiate(),
        );

        const data = (result as { data: { items: unknown[] } }).data;
        expect(data.items).toHaveLength(0);
    });
});

// ===========================================================================
// streamNowplaying — onCacheEntryAdded lifecycle + teardown
// ===========================================================================

/**
 * Flush all pending microtasks. RTK Query's onCacheEntryAdded / cacheDataLoaded
 * involves multiple chained promise resolutions before the subscribe call fires.
 * We drain the microtask queue with fake timers so everything settles before we
 * assert.
 */
async function flushMicrotasks(): Promise<void> {
    // 10 rounds is more than enough for RTK Query's internal promise chain.
    for (let i = 0; i < 10; i++) {
        await Promise.resolve();
    }
}

describe('streamNowplaying', () => {
    // Each streaming test uses fake timers so we can:
    //   a) drain the microtask queue deterministically via advanceTimersByTimeAsync(0)
    //   b) advance 60 s for cacheEntryRemoved in the teardown test
    // Re-establish the subscribe mock implementation inside this describe block
    // because vi.restoreAllMocks() (outer beforeEach) wipes vi.fn() implementations.
    beforeEach(async () => {
        vi.useFakeTimers();
        const { wsClient } = await import('@core/websocket/wsClient');
        vi.mocked(wsClient.subscribe).mockImplementation(
            (_type: string, cb: (msg: unknown) => void) => {
                mockSubscribeCallback = cb;
                return mockUnsub;
            },
        );
    });

    it('subscribes to spotify_state WS messages and dispatches spotifyStateReceived', async () => {
        const store = makeFullStore();
        const { nowplayingApi } = await import('../nowplayingApi');
        const { wsClient } = await import('@core/websocket/wsClient');

        // Initiate the streaming query — onCacheEntryAdded lifecycle starts.
        store.dispatch(nowplayingApi.endpoints.streamNowplaying.initiate());

        // Drain the RTK Query internal promise chain so cacheDataLoaded resolves
        // and subscribe() is invoked.
        await vi.advanceTimersByTimeAsync(0);
        await flushMicrotasks();

        // wsClient.subscribe must have been called with 'spotify_state'.
        expect(wsClient.subscribe).toHaveBeenCalledWith('spotify_state', expect.any(Function));
        expect(mockSubscribeCallback).not.toBeNull();
    });

    it('dispatches spotifyStateReceived with scope_upgrade_required:true when WS pushes that flag', async () => {
        const store = makeFullStore();
        const { nowplayingApi } = await import('../nowplayingApi');

        store.dispatch(nowplayingApi.endpoints.streamNowplaying.initiate());
        await vi.advanceTimersByTimeAsync(0);
        await flushMicrotasks();

        // Simulate backend pushing a spotify_state WS message.
        mockSubscribeCallback!({
            type: 'spotify_state',
            payload: {
                authenticated: true,
                scope_upgrade_required: true,
                track: {
                    name: 'Test Track',
                    artist: 'Test Artist',
                    album: 'Test Album',
                    durationMs: 200000,
                    progressMs: 60000,
                    isPlaying: true,
                    shuffle: false,
                    repeat: 'off',
                },
            },
        });

        const state = store.getState() as { nowplaying: { payload: { scope_upgrade_required?: boolean } | null } };
        expect(state.nowplaying.payload).not.toBeNull();
        expect(state.nowplaying.payload?.scope_upgrade_required).toBe(true);
    });

    it('calls unsub exactly once when cacheEntryRemoved resolves (no subscription leak)', async () => {
        const store = makeFullStore();
        const { nowplayingApi } = await import('../nowplayingApi');

        const subscriptionResult = store.dispatch(
            nowplayingApi.endpoints.streamNowplaying.initiate(),
        );
        // Let cacheDataLoaded resolve so subscribe() is called.
        await vi.advanceTimersByTimeAsync(0);
        await flushMicrotasks();

        expect(mockUnsub).not.toHaveBeenCalled();

        // Remove the only subscriber — RTK Query will clean the cache entry after
        // keepUnusedDataFor (default 60 s). Advance fake timers past that.
        subscriptionResult.unsubscribe();
        await vi.advanceTimersByTimeAsync(61_000);
        await flushMicrotasks();

        // cacheEntryRemoved has now resolved → unsub() must have been called once.
        expect(mockUnsub).toHaveBeenCalledTimes(1);
    });

    it('dispatches spotifyStateReceived for an unauthenticated state payload', async () => {
        const store = makeFullStore();
        const { nowplayingApi } = await import('../nowplayingApi');

        store.dispatch(nowplayingApi.endpoints.streamNowplaying.initiate());
        await vi.advanceTimersByTimeAsync(0);
        await flushMicrotasks();

        mockSubscribeCallback!({
            type: 'spotify_state',
            payload: { authenticated: false },
        });

        const state = store.getState() as { nowplaying: { payload: { authenticated: boolean } | null; hasLiveData: boolean } };
        expect(state.nowplaying.payload?.authenticated).toBe(false);
        expect(state.nowplaying.hasLiveData).toBe(true);
    });
});
