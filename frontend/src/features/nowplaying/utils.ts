import type {
    SpotifyStatePayload,
    NowPlayingTrack,
    SpotifyTrackResult,
    SpotifyQueueItem,
    SpotifyPlaylist,
    SpotifyAlbum,
    SpotifyArtist,
} from './types';
import type { SpotifySdkPlayerState } from './spotifySdk';

export function payloadToTrack(payload: SpotifyStatePayload): NowPlayingTrack | null {
    if (!payload.title && !payload.artist) return null;
    return {
        title: payload.title,
        artist: payload.artist,
        album: payload.album,
        monogram: deriveMonogram(payload.artist),
        albumArtUrl: payload.album_art_url,
        progressMs: payload.progress_ms,
        durationMs: payload.duration_ms,
        playing: payload.playing,
        shuffle: payload.shuffle,
        repeat: payload.repeat === 'context' ? 'all' : payload.repeat === 'track' ? 'one' : 'off',
        device: payload.device,
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

/**
 * Converts an SDK player state snapshot into the NowPlayingTrack shape
 * consumed by TrackInfo / ProgressBar / TransportControls.
 */
export function sdkStateToTrack(
    state: SpotifySdkPlayerState,
    deviceName: string,
): NowPlayingTrack | null {
    if (state.track === null) return null;
    const monogram = state.track.artist.slice(0, 3).toUpperCase();
    return {
        title: state.track.name,
        artist: state.track.artist,
        album: state.track.album,
        monogram,
        progressMs: state.positionMs,
        durationMs: state.durationMs,
        playing: !state.isPaused,
        shuffle: state.shuffle,
        repeat: state.repeat === 'context' ? 'all' : state.repeat === 'track' ? 'one' : 'off',
        device: deviceName,
    };
}

export function formatMs(ms: number): string {
    const totalSec = Math.floor(ms / 1000);
    const m = Math.floor(totalSec / 60);
    const s = totalSec % 60;
    return `${m}:${String(s).padStart(2, '0')}`;
}
