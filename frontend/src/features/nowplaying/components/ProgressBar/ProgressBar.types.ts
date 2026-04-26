import type { NowPlayingTrack } from '../../types';

export interface ProgressBarProps {
    track: NowPlayingTrack;
    /** When provided, the bar becomes interactive (click-to-seek + drag-to-scrub). */
    onSeek?: (positionMs: number) => void;
}
