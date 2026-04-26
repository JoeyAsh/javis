import type { NowPlayingTrack, SpotifyCmdAction } from '../../types';

export interface NowPlayingStripProps {
    track: NowPlayingTrack | null;
    onCmd: (cmd: SpotifyCmdAction, value?: number) => void;
}
