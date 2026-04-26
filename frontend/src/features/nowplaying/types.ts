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

/**
 * Flat, snake_case broadcast from `broadcast_spotify_state` in the backend.
 * All track fields are empty strings / zero when no track is active.
 */
export interface SpotifyStatePayload {
    authenticated: boolean;
    playing: boolean;
    title: string;
    artist: string;
    album: string;
    progress_ms: number;
    duration_ms: number;
    shuffle: boolean;
    repeat: 'off' | 'context' | 'track';
    device: string;
    scope_upgrade_required?: boolean;
    album_art_url?: string;
    error?: string;
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

// Re-export SDK types so feature consumers have a single import point.
export type { SpotifySdkError, SpotifySdkPlayerState } from './spotifySdk';
export type { PlayerSdkSlice } from './nowplayingSlice';
