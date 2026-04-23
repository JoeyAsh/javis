import type { SpotifyStatePayload } from '../types';

export interface UseNowPlayingReturn {
    payload: SpotifyStatePayload | null;
    hasLiveData: boolean;
    loading: boolean;
}
