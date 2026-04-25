import type { GitLabStatePayload } from '../types';

export interface UseGitlabReturn {
    state: GitLabStatePayload | null;
    loading: boolean;
}
