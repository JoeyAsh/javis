import type {
    SpotifyStatePayload,
    NowPlayingTrack,
    SpotifyTrackResult,
    SpotifyQueueItem,
    SpotifyPlaylist,
    SpotifyAlbum,
    SpotifyArtist,
} from './types';

export function payloadToTrack(payload: SpotifyStatePayload): NowPlayingTrack | null {
    const { track } = payload;
    if (!track) return null;
    const monogram = track.artist.slice(0, 3).toUpperCase();
    return {
        title: track.name,
        artist: track.artist,
        album: track.album,
        monogram,
        albumArtUrl: track.albumArtUrl,
        progressMs: track.progressMs,
        durationMs: track.durationMs,
        playing: track.isPlaying,
        shuffle: track.shuffle,
        repeat: track.repeat,
        device: payload.device?.name ?? '',
    };
}

export function isTrackResult(track: SpotifyTrackResult | SpotifyQueueItem): track is SpotifyTrackResult {
    return 'durationMs' in track;
}

export function isSearchTrack(item: SpotifyTrackResult | SpotifyArtist | SpotifyAlbum | SpotifyPlaylist): item is SpotifyTrackResult {
    return 'durationMs' in item;
}

export function isSearchPlaylist(item: SpotifyTrackResult | SpotifyArtist | SpotifyAlbum | SpotifyPlaylist): item is SpotifyPlaylist {
    return 'trackCount' in item && 'owner' in item;
}

export function isSearchAlbum(item: SpotifyTrackResult | SpotifyArtist | SpotifyAlbum | SpotifyPlaylist): item is SpotifyAlbum {
    return 'trackCount' in item && !('owner' in item);
}

/**
 * Derives a 3-character monogram from a string.
 * Strips non-alphanumeric chars, takes first 3, uppercases, and pads with
 * middle-dot if the result is shorter than 3 characters.
 */
export function deriveMonogram(s: string): string {
    return s.replace(/[^A-Za-z0-9]/g, '').slice(0, 3).toUpperCase().padEnd(3, '·');
}

export function formatMs(ms: number): string {
    const totalSec = Math.floor(ms / 1000);
    const m = Math.floor(totalSec / 60);
    const s = totalSec % 60;
    return `${m}:${String(s).padStart(2, '0')}`;
}
