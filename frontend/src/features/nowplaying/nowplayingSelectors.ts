import type { RootState } from '@app';
import type { SpotifyStatePayload } from './types';

export function selectNowPlayingPayload(state: RootState): SpotifyStatePayload | null {
    return state.nowplaying.payload;
}

export function selectNowPlayingHasLiveData(state: RootState): boolean {
    return state.nowplaying.hasLiveData;
}
