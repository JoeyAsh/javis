import type { NowPlayingTrack, SpotifyCmdAction } from '../../types';

export interface NowPlayingCompactProps {
    track: NowPlayingTrack;
    onCmd: (action: SpotifyCmdAction, value?: number) => void;
}
