import type { RootState } from '@app';
import type { SpotifyStatePayload, SpotifyTab, LibraryView } from './types';
import type { SpotifySdkError, SpotifySdkPlayerState } from './spotifySdk';

export function selectNowPlayingPayload(state: RootState): SpotifyStatePayload | null {
    return state.nowplaying.payload;
}

export function selectNowPlayingHasLiveData(state: RootState): boolean {
    return state.nowplaying.hasLiveData;
}

export function selectActiveTab(state: RootState): SpotifyTab {
    return state.nowplaying.activeTab;
}

export function selectLibraryView(state: RootState): LibraryView {
    return state.nowplaying.libraryView;
}

export function selectSelectedPlaylistId(state: RootState): string | null {
    return state.nowplaying.selectedPlaylistId;
}

export function selectSelectedPlaylistUri(state: RootState): string | null {
    return state.nowplaying.selectedPlaylistUri;
}

export function selectSelectedAlbumId(state: RootState): string | null {
    return state.nowplaying.selectedAlbumId;
}

export function selectSelectedAlbumUri(state: RootState): string | null {
    return state.nowplaying.selectedAlbumUri;
}

export function selectSearchQuery(state: RootState): string {
    return state.nowplaying.searchQuery;
}

export function selectPremiumError(state: RootState): boolean {
    return state.nowplaying.premiumError;
}

// --- SDK sub-state selectors ---

export function selectSdkDeviceId(state: RootState): string | null {
    return state.nowplaying.playerSdk.deviceId;
}

export function selectSdkIsReady(state: RootState): boolean {
    return state.nowplaying.playerSdk.isReady;
}

export function selectSdkError(state: RootState): SpotifySdkError | null {
    return state.nowplaying.playerSdk.lastError;
}

export function selectSdkPremiumRequired(state: RootState): boolean {
    return state.nowplaying.playerSdk.premiumRequired;
}

export function selectSdkPlayerState(state: RootState): SpotifySdkPlayerState | null {
    return state.nowplaying.playerSdk.sdkPlayerState;
}
