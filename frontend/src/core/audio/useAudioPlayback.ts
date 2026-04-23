/**
 * useAudioPlayback — side-effect hook that drains the Redux audio queue
 * into the Web Audio engine and handles barge-in flushing.
 *
 * Responsibilities:
 *   - Triggers the streaming query so audioPlaybackApi subscribes to WS.
 *   - Watches queue: when non-empty and not playing, dequeues the first item.
 *   - Watches pendingFlushId: when it changes, calls analyser.stopAll().
 *   - Watches isSpeaking from the analyser and syncs playingChanged into the slice.
 */

import { useEffect, useRef } from 'react';
import { useAppDispatch, useAppSelector } from '@app/hooks';
import { useStreamAudioPlaybackQuery } from './audioPlaybackApi';
import { audioConsumed, playingChanged } from './audioPlaybackSlice';
import { useAudioAnalyser } from './useAudioAnalyser';
import type { UseAudioPlaybackReturn } from './useAudioPlayback.types';

export function useAudioPlayback(): UseAudioPlaybackReturn {
    useStreamAudioPlaybackQuery();

    const dispatch = useAppDispatch();
    const queue = useAppSelector((s) => s.audioPlayback.queue);
    const pendingFlushId = useAppSelector((s) => s.audioPlayback.pendingFlushId);
    const isPlaying = useAppSelector((s) => s.audioPlayback.isPlaying);

    const { isSpeaking, enqueue, stopAll } = useAudioAnalyser();

    // ── Sync isSpeaking → slice ──────────────────────────────────────────────
    useEffect(() => {
        dispatch(playingChanged(isSpeaking));
    }, [isSpeaking, dispatch]);

    // ── Barge-in flush ───────────────────────────────────────────────────────
    const prevFlushIdRef = useRef(pendingFlushId);
    useEffect(() => {
        if (pendingFlushId !== prevFlushIdRef.current) {
            prevFlushIdRef.current = pendingFlushId;
            stopAll();
        }
    }, [pendingFlushId, stopAll]);

    // ── Drain queue → analyser ───────────────────────────────────────────────
    useEffect(() => {
        if (queue.length > 0 && !isPlaying) {
            const item = queue[0];
            enqueue(item.data, item.volume, item.channel);
            dispatch(audioConsumed());
        }
    }, [queue, isPlaying, enqueue, dispatch]);

    return { isPlaying };
}
