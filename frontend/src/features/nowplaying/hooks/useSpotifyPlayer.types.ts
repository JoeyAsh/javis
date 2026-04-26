import type { SpotifySdkError, SpotifySdkPlayerState } from '../spotifySdk';

export interface UseSpotifyPlayerReturn {
    deviceId: string | null;
    isReady: boolean;
    error: SpotifySdkError | null;
    sdkPlayerState: SpotifySdkPlayerState | null;
    setVolume: (value: number) => Promise<void>;
    togglePlay: () => Promise<void>;
    nextTrack: () => Promise<void>;
    previousTrack: () => Promise<void>;
    seek: (positionMs: number) => Promise<void>;
}
