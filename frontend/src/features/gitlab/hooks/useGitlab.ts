import { useAppSelector } from '@app';
import { useStreamGitlabStateQuery } from '../gitlabApi';
import { selectGitlabData, selectGitlabHasLiveData } from '../gitlabSelectors';
import type { UseGitlabReturn } from './useGitlab.types';

export function useGitlab(): UseGitlabReturn {
    // Kick off the RTK Query subscription so onCacheEntryAdded fires in prod.
    useStreamGitlabStateQuery();

    const data = useAppSelector(selectGitlabData);
    const hasLiveData = useAppSelector(selectGitlabHasLiveData);

    return { state: data, loading: !hasLiveData };
}
