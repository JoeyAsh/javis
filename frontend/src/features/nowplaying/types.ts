/**
 * Now Playing feature types.
 */

export interface NowPlayingTrack {
    title: string;
    artist: string;
    album: string;
    monogram: string;
    albumArtUrl?: string;
    progressMs: number;
    durationMs: number;
    playing: boolean;
    shuffle: boolean;
    repeat: 'off' | 'all' | 'one';
    device: string;
}

export interface SpotifyTrackPayload {
    name: string;
    artist: string;
    album: string;
    albumArtUrl?: string;
    durationMs: number;
    progressMs: number;
    isPlaying: boolean;
}

export interface SpotifyDevicePayload {
    name: string;
    type: string;
    volumePercent: number;
}

/**
 * Broadcast every `poll_interval_seconds` from the backend Spotify loop.
 * When `authenticated` is false, track and device are absent.
 */
export interface SpotifyStatePayload {
    authenticated: boolean;
    track?: SpotifyTrackPayload;
    device?: SpotifyDevicePayload;
    error?: string;
}

export type SpotifyCmdAction = 'play' | 'pause' | 'next' | 'prev' | 'volume';
