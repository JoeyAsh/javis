import type { NowPlayingTrack, SpotifyCmdAction } from '../../types';

export interface NowPlayingStripProps {
    track: NowPlayingTrack;
    onCmd: (cmd: SpotifyCmdAction, value?: number) => void;
}
