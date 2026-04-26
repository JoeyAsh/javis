import type { NowPlayingTrack, SpotifyCmdAction } from '../../types';

export interface SpotifyFullPanelProps {
    track: NowPlayingTrack | null;
    onCmd: (cmd: SpotifyCmdAction, value?: number) => void;
}
