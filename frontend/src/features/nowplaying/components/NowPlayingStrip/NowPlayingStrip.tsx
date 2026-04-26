import type { ReactElement } from 'react';
import { TrackInfo } from '../TrackInfo';
import { ProgressBar } from '../ProgressBar';
import { TransportControls } from '../TransportControls';
import type { NowPlayingStripProps } from './NowPlayingStrip.types';

export function NowPlayingStrip({ track, onCmd }: NowPlayingStripProps): ReactElement {
    if (track === null) {
        return (
            <div className="flex flex-col gap-0 border-b border-[var(--border)] pb-2 mb-2 flex-shrink-0">
                <div className="flex items-center justify-center h-[72px] font-mono text-xs tracking-widest text-cyan-700/50 uppercase select-none">
                    NO ACTIVE PLAYBACK
                </div>
            </div>
        );
    }

    return (
        <div className="flex flex-col gap-0 border-b border-[var(--border)] pb-2 mb-2 flex-shrink-0">
            <TrackInfo track={track} />
            <ProgressBar track={track} />
            <TransportControls track={track} onCmd={onCmd} />
        </div>
    );
}

export default NowPlayingStrip;
