import type { SpotifyTrackResult, SpotifyArtist, SpotifyAlbum, SpotifyPlaylist } from '../../types';

export type ResultGroupItem =
    | SpotifyTrackResult
    | SpotifyArtist
    | SpotifyAlbum
    | SpotifyPlaylist;

export interface ResultGroupProps {
    label: string;
    items: ResultGroupItem[];
    onTrackClick?: (uri: string) => void;
    onPlaylistClick?: (playlist: SpotifyPlaylist) => void;
    onAlbumClick?: (album: SpotifyAlbum) => void;
    onArtistClick?: (artist: SpotifyArtist) => void;
}
