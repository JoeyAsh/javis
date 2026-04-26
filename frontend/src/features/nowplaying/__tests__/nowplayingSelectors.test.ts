/**
 * nowplayingSelectors — unit tests (issue #58 new selectors).
 *
 * Pure selector tests — no rendering. Asserts correct value extraction.
 */
import { describe, expect, it } from 'vitest';
import {
    selectNowPlayingPayload,
    selectNowPlayingHasLiveData,
    selectActiveTab,
    selectLibraryView,
    selectSelectedPlaylistId,
    selectSelectedAlbumId,
    selectSearchQuery,
    selectPremiumError,
} from '../nowplayingSelectors';
import type { RootState } from '@app';

function makeState(overrides: Partial<RootState['nowplaying']> = {}): RootState {
    return {
        nowplaying: {
            payload: null,
            hasLiveData: false,
            activeTab: 'library',
            libraryView: 'playlists',
            selectedPlaylistId: null,
            selectedAlbumId: null,
            searchQuery: '',
            premiumError: false,
            ...overrides,
        },
    } as unknown as RootState;
}

// ---------------------------------------------------------------------------
// selectNowPlayingPayload (pre-existing)
// ---------------------------------------------------------------------------

describe('selectNowPlayingPayload', () => {
    it('returns null from initial state', () => {
        expect(selectNowPlayingPayload(makeState())).toBeNull();
    });

    it('returns the payload when set', () => {
        const payload = { authenticated: true } as const;
        expect(selectNowPlayingPayload(makeState({ payload }))).toEqual(payload);
    });
});

// ---------------------------------------------------------------------------
// selectNowPlayingHasLiveData (pre-existing)
// ---------------------------------------------------------------------------

describe('selectNowPlayingHasLiveData', () => {
    it('returns false from initial state', () => {
        expect(selectNowPlayingHasLiveData(makeState())).toBe(false);
    });

    it('returns true when hasLiveData=true', () => {
        expect(selectNowPlayingHasLiveData(makeState({ hasLiveData: true }))).toBe(true);
    });
});

// ---------------------------------------------------------------------------
// selectActiveTab (new — issue #58)
// ---------------------------------------------------------------------------

describe('selectActiveTab', () => {
    it('returns "library" from initial state', () => {
        expect(selectActiveTab(makeState())).toBe('library');
    });

    it('returns "search" when activeTab="search"', () => {
        expect(selectActiveTab(makeState({ activeTab: 'search' }))).toBe('search');
    });

    it('returns "queue" when activeTab="queue"', () => {
        expect(selectActiveTab(makeState({ activeTab: 'queue' }))).toBe('queue');
    });
});

// ---------------------------------------------------------------------------
// selectLibraryView (new — issue #58)
// ---------------------------------------------------------------------------

describe('selectLibraryView', () => {
    it('returns "playlists" from initial state', () => {
        expect(selectLibraryView(makeState())).toBe('playlists');
    });

    it('returns "playlist-tracks" when set', () => {
        expect(selectLibraryView(makeState({ libraryView: 'playlist-tracks' }))).toBe('playlist-tracks');
    });

    it('returns "album-tracks" when set', () => {
        expect(selectLibraryView(makeState({ libraryView: 'album-tracks' }))).toBe('album-tracks');
    });
});

// ---------------------------------------------------------------------------
// selectSelectedPlaylistId (new — issue #58)
// ---------------------------------------------------------------------------

describe('selectSelectedPlaylistId', () => {
    it('returns null from initial state', () => {
        expect(selectSelectedPlaylistId(makeState())).toBeNull();
    });

    it('returns the ID when set', () => {
        expect(selectSelectedPlaylistId(makeState({ selectedPlaylistId: 'pl-1' }))).toBe('pl-1');
    });
});

// ---------------------------------------------------------------------------
// selectSelectedAlbumId (new — issue #58)
// ---------------------------------------------------------------------------

describe('selectSelectedAlbumId', () => {
    it('returns null from initial state', () => {
        expect(selectSelectedAlbumId(makeState())).toBeNull();
    });

    it('returns the ID when set', () => {
        expect(selectSelectedAlbumId(makeState({ selectedAlbumId: 'al-1' }))).toBe('al-1');
    });
});

// ---------------------------------------------------------------------------
// selectSearchQuery (new — issue #58)
// ---------------------------------------------------------------------------

describe('selectSearchQuery', () => {
    it('returns empty string from initial state', () => {
        expect(selectSearchQuery(makeState())).toBe('');
    });

    it('returns the query when set', () => {
        expect(selectSearchQuery(makeState({ searchQuery: 'Midnight City' }))).toBe('Midnight City');
    });
});

// ---------------------------------------------------------------------------
// selectPremiumError (new — issue #58)
// ---------------------------------------------------------------------------

describe('selectPremiumError', () => {
    it('returns false from initial state', () => {
        expect(selectPremiumError(makeState())).toBe(false);
    });

    it('returns true when premiumError=true', () => {
        expect(selectPremiumError(makeState({ premiumError: true }))).toBe(true);
    });
});
