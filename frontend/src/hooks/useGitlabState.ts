/**
 * useGitlabState — subscribes to live `gitlab_state` WebSocket messages and
 * exposes the latest payload plus a loading flag.
 *
 * Follows the same pattern as `useGitHubState` / `useSpotifyState`:
 *  - Registers via `subscribeGitLabStateStream` (module-level registry).
 *  - `loading` is `true` until the first payload arrives.
 *  - Returns `{ data: null, loading: true }` when the feature is disabled or
 *    the backend has not yet sent a frame.
 */
import { useEffect, useRef, useState } from 'react';

import type { GitLabStatePayload } from '../types';
import { subscribeGitLabStateStream } from './useWebSocket';

/** How long to wait for first GitLab frame before marking backend unavailable. */
const AVAILABILITY_TIMEOUT_MS = 10_000;

export interface UseGitlabStateReturn {
    /** Latest GitLab state payload, or `null` before first message. */
    data: GitLabStatePayload | null;
    /** True until the first `gitlab_state` frame is received. */
    loading: boolean;
    /** False after timeout with no data — panel should hide itself. */
    available: boolean;
}

/**
 * Hook that tracks the latest `gitlab_state` WebSocket payload.
 *
 * @returns `{ data, loading, available }` — `data` is null before first message.
 *   `available` becomes false if no frame arrives within AVAILABILITY_TIMEOUT_MS.
 */
export function useGitlabState(): UseGitlabStateReturn {
    const [data, setData] = useState<GitLabStatePayload | null>(null);
    const [loading, setLoading] = useState(true);
    const [available, setAvailable] = useState(true);
    const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    useEffect(() => {
        timerRef.current = setTimeout(() => {
            setAvailable(false);
        }, AVAILABILITY_TIMEOUT_MS);

        const unsubscribe = subscribeGitLabStateStream((payload) => {
            if (timerRef.current) clearTimeout(timerRef.current);
            setData(payload);
            setLoading(false);
            setAvailable(true);
        });
        return () => {
            if (timerRef.current) clearTimeout(timerRef.current);
            unsubscribe();
        };
    }, []);

    return { data, loading, available };
}
