/**
 * nowplayingSlice — reducer unit tests (issue #58 additions + initial-state regression).
 *
 * Pure reducer tests — no rendering, no store.
 */
import { describe, expect, it } from 'vitest';
import reducer, {
    spotifyStateReceived,
    setActiveTab,
    setLibraryView,
    selectPlaylist,
    selectAlbum,
    setSearchQuery,
    setPremiumError,
} from '../nowplayingSlice';
import type { NowPlayingState } from '../nowplayingSlice';
import type { SpotifyStatePayload } from '../types';

const initialState: NowPlayingState = {
    payload: null,
    hasLiveData: false,
    activeTab: 'library',
    libraryView: 'playlists',
    selectedPlaylistId: null,
    selectedPlaylistUri: null,
    selectedAlbumId: null,
    selectedAlbumUri: null,
    searchQuery: '',
    premiumError: false,
    playerSdk: {
        deviceId: null,
        isReady: false,
        lastError: null,
        premiumRequired: false,
        sdkPlayerState: null,
    },
};

// ---------------------------------------------------------------------------
// Initial state regression
// ---------------------------------------------------------------------------

describe('nowplayingSlice — initial state', () => {
    it('produces the expected initial state', () => {
        const state = reducer(undefined, { type: '@@INIT' });
        expect(state.payload).toBeNull();
        expect(state.hasLiveData).toBe(false);
        expect(state.activeTab).toBe('library');
        expect(state.libraryView).toBe('playlists');
        expect(state.selectedPlaylistId).toBeNull();
        expect(state.selectedAlbumId).toBeNull();
        expect(state.searchQuery).toBe('');
        expect(state.premiumError).toBe(false);
    });
});

// ---------------------------------------------------------------------------
// spotifyStateReceived (pre-existing, regression check)
// ---------------------------------------------------------------------------

describe('spotifyStateReceived', () => {
    it('sets payload and marks hasLiveData=true', () => {
        const payload: SpotifyStatePayload = {
            authenticated: true,
            playing: false,
            title: '',
            artist: '',
            album: '',
            progress_ms: 0,
            duration_ms: 0,
            shuffle: false,
            repeat: 'off',
            device: '',
        };
        const state = reducer(initialState, spotifyStateReceived(payload));
        expect(state.payload).toEqual(payload);
        expect(state.hasLiveData).toBe(true);
    });

    it('updates payload on subsequent calls', () => {
        const p1: SpotifyStatePayload = {
            authenticated: true,
            playing: false,
            title: '',
            artist: '',
            album: '',
            progress_ms: 0,
            duration_ms: 0,
            shuffle: false,
            repeat: 'off',
            device: '',
        };
        const p2: SpotifyStatePayload = {
            authenticated: false,
            playing: false,
            title: '',
            artist: '',
            album: '',
            progress_ms: 0,
            duration_ms: 0,
            shuffle: false,
            repeat: 'off',
            device: '',
        };
        const s1 = reducer(initialState, spotifyStateReceived(p1));
        const s2 = reducer(s1, spotifyStateReceived(p2));
        expect(s2.payload?.authenticated).toBe(false);
        expect(s2.hasLiveData).toBe(true);
    });
});

// ---------------------------------------------------------------------------
// setActiveTab (new — issue #58)
// ---------------------------------------------------------------------------

describe('setActiveTab', () => {
    it('sets activeTab to "search"', () => {
        const state = reducer(initialState, setActiveTab('search'));
        expect(state.activeTab).toBe('search');
    });

    it('sets activeTab to "queue"', () => {
        const state = reducer(initialState, setActiveTab('queue'));
        expect(state.activeTab).toBe('queue');
    });

    it('sets activeTab back to "library"', () => {
        const s1 = reducer(initialState, setActiveTab('search'));
        const s2 = reducer(s1, setActiveTab('library'));
        expect(s2.activeTab).toBe('library');
    });

    it('does not mutate other state fields', () => {
        const state = reducer(initialState, setActiveTab('search'));
        expect(state.premiumError).toBe(false);
        expect(state.searchQuery).toBe('');
    });
});

// ---------------------------------------------------------------------------
// setLibraryView (new — issue #58)
// ---------------------------------------------------------------------------

describe('setLibraryView', () => {
    it('sets libraryView to "playlist-tracks"', () => {
        const state = reducer(initialState, setLibraryView('playlist-tracks'));
        expect(state.libraryView).toBe('playlist-tracks');
    });

    it('sets libraryView to "album-tracks"', () => {
        const state = reducer(initialState, setLibraryView('album-tracks'));
        expect(state.libraryView).toBe('album-tracks');
    });

    it('sets libraryView to "saved-tracks"', () => {
        const state = reducer(initialState, setLibraryView('saved-tracks'));
        expect(state.libraryView).toBe('saved-tracks');
    });

    it('sets libraryView to "saved-albums"', () => {
        const state = reducer(initialState, setLibraryView('saved-albums'));
        expect(state.libraryView).toBe('saved-albums');
    });

    it('resets libraryView back to "playlists"', () => {
        const s1 = reducer(initialState, setLibraryView('album-tracks'));
        const s2 = reducer(s1, setLibraryView('playlists'));
        expect(s2.libraryView).toBe('playlists');
    });
});

// ---------------------------------------------------------------------------
// selectPlaylist (new — issue #58)
// ---------------------------------------------------------------------------

describe('selectPlaylist', () => {
    it('sets selectedPlaylistId to a string ID', () => {
        const state = reducer(initialState, selectPlaylist('pl-1'));
        expect(state.selectedPlaylistId).toBe('pl-1');
    });

    it('clears selectedPlaylistId when null is dispatched', () => {
        const s1 = reducer(initialState, selectPlaylist('pl-1'));
        const s2 = reducer(s1, selectPlaylist(null));
        expect(s2.selectedPlaylistId).toBeNull();
    });
});

// ---------------------------------------------------------------------------
// selectAlbum (new — issue #58)
// ---------------------------------------------------------------------------

describe('selectAlbum', () => {
    it('sets selectedAlbumId to a string ID', () => {
        const state = reducer(initialState, selectAlbum('al-1'));
        expect(state.selectedAlbumId).toBe('al-1');
    });

    it('clears selectedAlbumId when null is dispatched', () => {
        const s1 = reducer(initialState, selectAlbum('al-1'));
        const s2 = reducer(s1, selectAlbum(null));
        expect(s2.selectedAlbumId).toBeNull();
    });
});

// ---------------------------------------------------------------------------
// setSearchQuery (new — issue #58)
// ---------------------------------------------------------------------------

describe('setSearchQuery', () => {
    it('sets searchQuery to a non-empty string', () => {
        const state = reducer(initialState, setSearchQuery('Midnight City'));
        expect(state.searchQuery).toBe('Midnight City');
    });

    it('clears searchQuery to empty string', () => {
        const s1 = reducer(initialState, setSearchQuery('Midnight City'));
        const s2 = reducer(s1, setSearchQuery(''));
        expect(s2.searchQuery).toBe('');
    });
});

// ---------------------------------------------------------------------------
// setPremiumError (new — issue #58)
// ---------------------------------------------------------------------------

describe('setPremiumError', () => {
    it('sets premiumError to true', () => {
        const state = reducer(initialState, setPremiumError(true));
        expect(state.premiumError).toBe(true);
    });

    it('clears premiumError to false', () => {
        const s1 = reducer(initialState, setPremiumError(true));
        const s2 = reducer(s1, setPremiumError(false));
        expect(s2.premiumError).toBe(false);
    });

    it('does not affect other fields', () => {
        const s1 = reducer(initialState, setSearchQuery('test'));
        const s2 = reducer(s1, setPremiumError(true));
        expect(s2.searchQuery).toBe('test');
    });
});
