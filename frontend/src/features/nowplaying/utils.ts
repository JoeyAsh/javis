import type { SpotifyStatePayload, NowPlayingTrack } from './types';

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
        shuffle: false,
        repeat: 'off',
        device: payload.device?.name ?? '',
    };
}

export function formatMs(ms: number): string {
    const totalSec = Math.floor(ms / 1000);
    const m = Math.floor(totalSec / 60);
    const s = totalSec % 60;
    return `${m}:${String(s).padStart(2, '0')}`;
}
