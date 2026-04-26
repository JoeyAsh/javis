import type { SpotifyTrackResult, SpotifyQueueItem } from '../../types';

export interface TrackRowProps {
    track: SpotifyTrackResult | SpotifyQueueItem;
    index?: number;
    onClick: (uri: string) => void;
    onAddToQueue?: (uri: string) => void;
}
