/**
 * nowplayingApi — RTK Query endpoint tests (issue #58 new endpoints).
 *
 * Verifies URL shapes and query-param serialisation for all 10 new endpoints.
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
});

afterEach(() => {
    global.Request = OriginalRequest;
});

// ---------------------------------------------------------------------------
// Minimal store setup — fresh per test to avoid RTK Query cache hits.
// ---------------------------------------------------------------------------

function makeStore() {
    return configureStore({
        reducer: { [baseApi.reducerPath]: baseApi.reducer },
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
