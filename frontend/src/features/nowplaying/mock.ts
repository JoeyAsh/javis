import type {
    NowPlayingTrack,
    SpotifyPlaylist,
    SpotifyTrackResult,
    SpotifySearchResults,
    SpotifyQueueItem,
} from './types';
import type { SpotifySdkPlayerState } from './spotifySdk';

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

export const mockPlaylists: SpotifyPlaylist[] = [
    {
        id: 'pl-1',
        name: 'Coding Sessions',
        owner: 'jarvis_user',
        trackCount: 42,
        uri: 'spotify:playlist:pl-1',
        monogram: 'COD',
    },
    {
        id: 'pl-2',
        name: 'Deep Focus',
        owner: 'jarvis_user',
        trackCount: 28,
        uri: 'spotify:playlist:pl-2',
        monogram: 'DEF',
    },
    {
        id: 'pl-3',
        name: 'Morning Routine',
        owner: 'jarvis_user',
        trackCount: 15,
        uri: 'spotify:playlist:pl-3',
        monogram: 'MOR',
    },
];

export const mockTrackResults: SpotifyTrackResult[] = [
    {
        id: 'tr-1',
        name: 'Midnight City',
        artist: 'M83',
        album: "Hurry Up, We're Dreaming",
        durationMs: 241_000,
        uri: 'spotify:track:tr-1',
        monogram: 'M83',
    },
    {
        id: 'tr-2',
        name: 'Oblivion',
        artist: 'Grimes',
        album: 'Visions',
        durationMs: 253_000,
        uri: 'spotify:track:tr-2',
        monogram: 'GRM',
    },
    {
        id: 'tr-3',
        name: 'Intro',
        artist: 'The xx',
        album: 'xx',
        durationMs: 130_000,
        uri: 'spotify:track:tr-3',
        monogram: 'TXX',
    },
];

export const mockSearchResults: SpotifySearchResults = {
    tracks: mockTrackResults,
    artists: [
        { id: 'ar-1', name: 'M83', uri: 'spotify:artist:ar-1', monogram: 'M83' },
        { id: 'ar-2', name: 'Grimes', uri: 'spotify:artist:ar-2', monogram: 'GRM' },
    ],
    albums: [
        {
            id: 'al-1',
            name: "Hurry Up, We're Dreaming",
            artist: 'M83',
            uri: 'spotify:album:al-1',
            trackCount: 22,
            monogram: 'HUW',
        },
    ],
    playlists: mockPlaylists.slice(0, 1),
};

export const mockSdkPlayerState: SpotifySdkPlayerState = {
    isPaused: false,
    positionMs: 113_000,
    durationMs: 241_000,
    track: {
        uri: 'spotify:track:tr-1',
        name: 'Midnight City',
        artist: 'M83',
        album: "Hurry Up, We're Dreaming",
    },
    shuffle: false,
    repeat: 'off',
};

export const mockQueueItems: SpotifyQueueItem[] = [
    { position: 0, name: 'Oblivion', artist: 'Grimes', uri: 'spotify:track:tr-2', monogram: 'GRM' },
    { position: 1, name: 'Intro', artist: 'The xx', uri: 'spotify:track:tr-3', monogram: 'TXX' },
    { position: 2, name: 'Begin Again', artist: 'Purity Ring', uri: 'spotify:track:tr-4', monogram: 'PUR' },
];
