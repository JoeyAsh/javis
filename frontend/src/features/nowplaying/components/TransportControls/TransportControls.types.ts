import type { SpotifyCmdAction, NowPlayingTrack } from '../../types';

export interface TransportControlsProps {
    track: NowPlayingTrack;
    onCmd: (action: SpotifyCmdAction, value?: number) => void;
    volume: number;
    onVolume: (value: number) => void;
}
