import { createSlice } from '@reduxjs/toolkit';
import type { PayloadAction } from '@reduxjs/toolkit';
import type { SpotifyStatePayload, SpotifyTab, LibraryView } from './types';

export interface NowPlayingState {
    payload: SpotifyStatePayload | null;
    hasLiveData: boolean;
    activeTab: SpotifyTab;
    libraryView: LibraryView;
    selectedPlaylistId: string | null;
    selectedAlbumId: string | null;
    searchQuery: string;
    premiumError: boolean;
}

const initialState: NowPlayingState = {
    payload: null,
    hasLiveData: false,
    activeTab: 'library',
    libraryView: 'playlists',
    selectedPlaylistId: null,
    selectedAlbumId: null,
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
        selectPlaylist(state, action: PayloadAction<string | null>) {
            state.selectedPlaylistId = action.payload;
        },
        selectAlbum(state, action: PayloadAction<string | null>) {
            state.selectedAlbumId = action.payload;
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
    selectAlbum,
    setSearchQuery,
    setPremiumError,
} = nowplayingSlice.actions;
export default nowplayingSlice.reducer;
