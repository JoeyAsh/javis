import type { NowPlayingTrack, SpotifyCmdAction } from '../../types';

export interface SpotifyFullPanelProps {
    track: NowPlayingTrack;
    onCmd: (cmd: SpotifyCmdAction, value?: number) => void;
}
