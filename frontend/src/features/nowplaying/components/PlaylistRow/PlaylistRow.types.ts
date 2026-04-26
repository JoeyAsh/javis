import type { SpotifyPlaylist } from '../../types';

export interface PlaylistRowProps {
    playlist: SpotifyPlaylist;
    onClick: (playlist: SpotifyPlaylist) => void;
}
