/**
 * @deprecated — consume via @core/api useStreamGithubStateQuery instead.
 *
 * This shim remains so DevPanel and other existing consumers continue to
 * compile without changes until batch 2c migrates DevPanel.
 */
import { useStreamGithubStateQuery } from '@core/api/githubApi';
import type { GitHubStatePayload } from '../types';

export interface UseGitHubStateReturn {
    data: GitHubStatePayload | null;
    loading: boolean;
}

export function useGitHubState(): UseGitHubStateReturn {
    const { data, isLoading } = useStreamGithubStateQuery();
    return { data: data ?? null, loading: isLoading };
}

export default useGitHubState;
