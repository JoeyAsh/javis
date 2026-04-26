import type { ReactElement } from 'react';
import { useSpotifyFull } from '../../hooks/useSpotifyFull';
import { TrackRow } from '../TrackRow';
import type { QueueTabProps } from './QueueTab.types';

export function QueueTab(_props: QueueTabProps): ReactElement {
    const { queue, isLoadingQueue, playUris } = useSpotifyFull();

    if (isLoadingQueue) {
        return (
            <div className="flex items-center justify-center flex-1 text-[10px] text-[var(--text-muted)] font-[var(--font)] tracking-widest">
                LOADING...
            </div>
        );
    }

    if (queue.length === 0) {
        return (
            <div className="flex items-center justify-center flex-1 text-[10px] text-[var(--text-muted)] font-[var(--font)] tracking-widest">
                QUEUE EMPTY
            </div>
        );
    }

    return (
        <div className="overflow-y-auto flex-1">
            {queue.map((item) => (
                <TrackRow
                    key={`${item.position}-${item.uri}`}
                    track={item}
                    index={item.position}
                    onClick={(uri) => playUris([uri])}
                />
            ))}
        </div>
    );
}

export default QueueTab;
