import { createSlice } from '@reduxjs/toolkit';
import type { PayloadAction } from '@reduxjs/toolkit';
import type { SpotifyStatePayload, SpotifyTab, LibraryView } from './types';

export interface NowPlayingState {
    payload: SpotifyStatePayload | null;
    hasLiveData: boolean;
    activeTab: SpotifyTab;
    libraryView: LibraryView;
    selectedPlaylistId: string | null;
    selectedPlaylistUri: string | null;
    selectedAlbumId: string | null;
    selectedAlbumUri: string | null;
    searchQuery: string;
    premiumError: boolean;
}

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
};

const nowplayingSlice = createSlice({
    name: 'nowplaying',
    initialState,
    reducers: {
        spotifyStateReceived(state, action: PayloadAction<SpotifyStatePayload>) {
            state.payload = action.payload;
            state.hasLiveData = true;
        },
        setActiveTab(state, action: PayloadAction<SpotifyTab>) {
            state.activeTab = action.payload;
        },
        setLibraryView(state, action: PayloadAction<LibraryView>) {
            state.libraryView = action.payload;
        },
        /** Stores the selected playlist ID; pass null to clear. */
        selectPlaylist(state, action: PayloadAction<string | null>) {
            state.selectedPlaylistId = action.payload;
            if (action.payload === null) {
                state.selectedPlaylistUri = null;
            }
        },
        /** Stores the URI for the currently-selected playlist (for playContext). */
        setSelectedPlaylistUri(state, action: PayloadAction<string | null>) {
            state.selectedPlaylistUri = action.payload;
        },
        /** Stores the selected album ID; pass null to clear. */
        selectAlbum(state, action: PayloadAction<string | null>) {
            state.selectedAlbumId = action.payload;
            if (action.payload === null) {
                state.selectedAlbumUri = null;
            }
        },
        /** Stores the URI for the currently-selected album (for playContext). */
        setSelectedAlbumUri(state, action: PayloadAction<string | null>) {
            state.selectedAlbumUri = action.payload;
        },
        setSearchQuery(state, action: PayloadAction<string>) {
            state.searchQuery = action.payload;
        },
        setPremiumError(state, action: PayloadAction<boolean>) {
            state.premiumError = action.payload;
        },
    },
});

export const {
    spotifyStateReceived,
    setActiveTab,
    setLibraryView,
    selectPlaylist,
    setSelectedPlaylistUri,
    selectAlbum,
    setSelectedAlbumUri,
    setSearchQuery,
    setPremiumError,
} = nowplayingSlice.actions;
export default nowplayingSlice.reducer;
