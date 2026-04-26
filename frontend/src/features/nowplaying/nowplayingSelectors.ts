import type { RootState } from '@app';
import type { SpotifyStatePayload, SpotifyTab, LibraryView } from './types';

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

export function selectSelectedAlbumId(state: RootState): string | null {
    return state.nowplaying.selectedAlbumId;
}

export function selectSearchQuery(state: RootState): string {
    return state.nowplaying.searchQuery;
}

export function selectPremiumError(state: RootState): boolean {
    return state.nowplaying.premiumError;
}
