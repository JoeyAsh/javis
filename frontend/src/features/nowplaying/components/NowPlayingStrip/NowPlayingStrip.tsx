import { useCallback, useRef, useState } from 'react';
import type { ReactElement } from 'react';
import { TrackInfo } from '../TrackInfo';
import { ProgressBar } from '../ProgressBar';
import { TransportControls } from '../TransportControls';
import { INITIAL_UI_VOLUME } from '../../constants';
import type { NowPlayingStripProps } from './NowPlayingStrip.types';

export function NowPlayingStrip({ track, onCmd }: NowPlayingStripProps): ReactElement {
    const [volume, setVolume] = useState<number>(INITIAL_UI_VOLUME);
    const volumeBeforeMuteRef = useRef<number>(INITIAL_UI_VOLUME);

    const handleVolume = useCallback(
        (value: number): void => {
            if (value > 0) {
                volumeBeforeMuteRef.current = value;
            }
            setVolume(value);
            onCmd('volume', value);
        },
        [onCmd],
    );

    const handleSeek = useCallback(
        (positionMs: number): void => {
            onCmd('seek', positionMs);
        },
        [onCmd],
    );

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
            <ProgressBar track={track} onSeek={handleSeek} />
            <TransportControls
                track={track}
                onCmd={onCmd}
                volume={volume}
                onVolume={handleVolume}
            />
        </div>
    );
}

export default NowPlayingStrip;
