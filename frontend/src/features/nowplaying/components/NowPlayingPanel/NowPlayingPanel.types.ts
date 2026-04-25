import type { PanelMode } from '@common/types';
import type { NowPlayingTrack, SpotifyCmdAction } from '../../types';

export interface NowPlayingPanelProps {
    mode?: PanelMode;
}

export interface NowPlayingCompactProps {
    track: NowPlayingTrack;
    onCmd: (action: SpotifyCmdAction, value?: number) => void;
}

export interface NowPlayingExpandedProps {
    track: NowPlayingTrack;
    onCmd: (action: SpotifyCmdAction, value?: number) => void;
}
