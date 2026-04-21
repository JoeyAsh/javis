/**
 * useGitHubState — subscribes to live `github_state` WebSocket messages and
 * exposes the latest payload plus a loading flag.
 *
 * Follows the same pattern as `useSpotifyState` / `useMailState`:
 *  - Registers via `subscribeGitHubStateStream` (module-level registry).
 *  - `loading` is `true` until the first payload arrives.
 *  - Returns `{ data: null, loading: true }` when the feature is disabled or
 *    the backend has not yet sent a frame.
 */
import { useEffect, useState } from 'react';

import type { GitHubStatePayload } from '../types';
import { subscribeGitHubStateStream } from './useWebSocket';

export interface UseGitHubStateReturn {
    /** Latest GitHub state payload, or `null` before first message. */
    data: GitHubStatePayload | null;
    /** True until the first `github_state` frame is received. */
    loading: boolean;
}

/**
 * Hook that tracks the latest `github_state` WebSocket payload.
 *
 * @returns `{ data, loading }` — `data` is null before first message.
 */
export function useGitHubState(): UseGitHubStateReturn {
    const [data, setData] = useState<GitHubStatePayload | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const unsubscribe = subscribeGitHubStateStream((payload) => {
            setData(payload);
            setLoading(false);
        });
        return unsubscribe;
    }, []);

    return { data, loading };
}
