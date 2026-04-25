import type { RootState } from '@app/store';
import type { GitLabStatePayload } from './types';

export function selectGitlabData(state: RootState): GitLabStatePayload | null {
    return state.gitlab.data;
}

export function selectGitlabHasLiveData(state: RootState): boolean {
    return state.gitlab.hasLiveData;
}
