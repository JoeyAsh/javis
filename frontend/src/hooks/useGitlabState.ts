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
import { useEffect, useState } from 'react';

import type { GitLabStatePayload } from '../types';
import { subscribeGitLabStateStream } from './useWebSocket';

export interface UseGitlabStateReturn {
  /** Latest GitLab state payload, or `null` before first message. */
  data: GitLabStatePayload | null;
  /** True until the first `gitlab_state` frame is received. */
  loading: boolean;
}

/**
 * Hook that tracks the latest `gitlab_state` WebSocket payload.
 *
 * @returns `{ data, loading }` — `data` is null before first message.
 */
export function useGitlabState(): UseGitlabStateReturn {
  const [data, setData] = useState<GitLabStatePayload | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const unsubscribe = subscribeGitLabStateStream((payload) => {
      setData(payload);
      setLoading(false);
    });
    return unsubscribe;
  }, []);

  return { data, loading };
}
