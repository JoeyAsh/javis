import { useMemo } from 'react';
import { useMockTicker } from '@common/hooks/useMockTicker';

/** Ticks forward 1 s per interval while the track is playing. */
export function useLiveProgress(playing: boolean, progressMs: number, durationMs: number): number {
    const tick = useMockTicker(1000, !playing);
    return useMemo<number>(() => {
        if (!playing) return progressMs;
        return (progressMs + tick * 1000) % durationMs;
    }, [tick, playing, progressMs, durationMs]);
}
