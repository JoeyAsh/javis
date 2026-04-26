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
    shuffle: boolean;
    repeat: 'off' | 'all' | 'one';
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
    scope_upgrade_required?: boolean;
}

export type SpotifyCmdAction = 'play' | 'pause' | 'next' | 'prev' | 'volume';

export interface SpotifyPlaylist {
    id: string;
    name: string;
    owner: string;
    trackCount: number;
    uri: string;
    monogram: string;
}

export interface SpotifyTrackResult {
    id: string;
    name: string;
    artist: string;
    album: string;
    durationMs: number;
    uri: string;
    monogram: string;
}

export interface SpotifyAlbum {
    id: string;
    name: string;
    artist: string;
    uri: string;
    trackCount: number;
    monogram: string;
}

export interface SpotifyArtist {
    id: string;
    name: string;
    uri: string;
    monogram: string;
}

export interface SpotifyQueueItem {
    position: number;
    name: string;
    artist: string;
    uri: string;
    monogram: string;
}

export interface SpotifySearchResults {
    tracks: SpotifyTrackResult[];
    artists: SpotifyArtist[];
    albums: SpotifyAlbum[];
    playlists: SpotifyPlaylist[];
}

export interface SpotifyLibraryPage<T> {
    items: T[];
    total: number;
    offset: number;
}

export type SpotifyTab = 'library' | 'search' | 'queue';
export type LibraryView = 'playlists' | 'playlist-tracks' | 'album-tracks' | 'saved-tracks' | 'saved-albums';
