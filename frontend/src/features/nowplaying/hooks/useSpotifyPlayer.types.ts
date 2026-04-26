import type { SpotifySdkError, SpotifySdkPlayerState } from '../spotifySdk';

export interface UseSpotifyPlayerReturn {
    deviceId: string | null;
    isReady: boolean;
    error: SpotifySdkError | null;
    sdkPlayerState: SpotifySdkPlayerState | null;
    setVolume: (value: number) => void;
    togglePlay: () => void;
    nextTrack: () => void;
    previousTrack: () => void;
    seek: (positionMs: number) => void;
}
