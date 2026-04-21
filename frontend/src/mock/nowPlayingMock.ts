import type { NowPlayingTrack } from '../types';

export const nowPlayingMock: NowPlayingTrack = {
    title: 'Midnight City',
    artist: 'M83',
    album: "Hurry Up, We're Dreaming",
    monogram: 'M83',
    progressMs: 113_000,
    durationMs: 241_000,
    playing: true,
    shuffle: false,
    repeat: 'off',
    device: 'Studio Monitors',
};
