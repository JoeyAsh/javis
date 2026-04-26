/**
 * Window-level type augmentation for the Spotify Web Playback SDK.
 * Keeps global pollution out of the runtime module.
 *
 * All declarations are wrapped in `declare global {}` so this file is treated
 * as an ES-module augmentation and the types are available everywhere in the
 * project without an explicit import.
 */

export {};

declare global {
    interface SpotifyPlayerOptions {
        name: string;
        getOAuthToken: (cb: (token: string) => void) => void;
        volume?: number;
    }

    interface SpotifyTrackWindow {
        current_track: SpotifyTrackFull;
    }

    interface SpotifyTrackFull {
        uri: string;
        name: string;
        artists: Array<{ name: string }>;
        album: { name: string };
    }

    interface SpotifyPlaybackState {
        paused: boolean;
        position: number;
        duration: number;
        track_window: SpotifyTrackWindow;
        shuffle: boolean;
        repeat_mode: 0 | 1 | 2;
    }

    interface SpotifyPlayerErrorEvent {
        message: string;
    }

    interface SpotifyReadyEvent {
        device_id: string;
    }

    interface SpotifyPlayerInstance {
        connect(): Promise<boolean>;
        disconnect(): void;
        setVolume(value: number): Promise<void>;
        togglePlay(): Promise<void>;
        nextTrack(): Promise<void>;
        previousTrack(): Promise<void>;
        seek(positionMs: number): Promise<void>;
        addListener(event: 'ready', cb: (e: SpotifyReadyEvent) => void): void;
        addListener(event: 'not_ready', cb: (e: SpotifyReadyEvent) => void): void;
        addListener(event: 'player_state_changed', cb: (state: SpotifyPlaybackState | null) => void): void;
        addListener(event: 'initialization_error', cb: (e: SpotifyPlayerErrorEvent) => void): void;
        addListener(event: 'authentication_error', cb: (e: SpotifyPlayerErrorEvent) => void): void;
        addListener(event: 'account_error', cb: (e: SpotifyPlayerErrorEvent) => void): void;
        addListener(event: 'playback_error', cb: (e: SpotifyPlayerErrorEvent) => void): void;
    }

    interface SpotifyNamespace {
        Player: new (options: SpotifyPlayerOptions) => SpotifyPlayerInstance;
    }

    interface Window {
        Spotify: SpotifyNamespace;
        onSpotifyWebPlaybackSDKReady: (() => void) | undefined;
    }
}
