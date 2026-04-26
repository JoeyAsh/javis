import { createSlice } from '@reduxjs/toolkit';
import type { PayloadAction } from '@reduxjs/toolkit';
import type { SpotifyStatePayload, SpotifyTab, LibraryView } from './types';
import type { SpotifySdkError, SpotifySdkPlayerState } from './spotifySdk';

export interface PlayerSdkSlice {
    deviceId: string | null;
    isReady: boolean;
    lastError: SpotifySdkError | null;
    premiumRequired: boolean;
    sdkPlayerState: SpotifySdkPlayerState | null;
}

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
    playerSdk: PlayerSdkSlice;
}

const initialPlayerSdk: PlayerSdkSlice = {
    deviceId: null,
    isReady: false,
    lastError: null,
    premiumRequired: false,
    sdkPlayerState: null,
};

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
    playerSdk: initialPlayerSdk,
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
        // --- SDK sub-state reducers ---
        setSdkDeviceId(state, action: PayloadAction<string | null>) {
            state.playerSdk.deviceId = action.payload;
        },
        setSdkReady(state, action: PayloadAction<boolean>) {
            state.playerSdk.isReady = action.payload;
        },
        setSdkError(state, action: PayloadAction<SpotifySdkError | null>) {
            state.playerSdk.lastError = action.payload;
        },
        setPremiumRequired(state, action: PayloadAction<boolean>) {
            state.playerSdk.premiumRequired = action.payload;
        },
        setSdkPlayerState(state, action: PayloadAction<SpotifySdkPlayerState | null>) {
            state.playerSdk.sdkPlayerState = action.payload;
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
    setSdkDeviceId,
    setSdkReady,
    setSdkError,
    setPremiumRequired,
    setSdkPlayerState,
} = nowplayingSlice.actions;
export default nowplayingSlice.reducer;
