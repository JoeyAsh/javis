import { useStreamGithubStateQuery } from '@core/api/githubApi';
import { devMock } from '../mock';
import type { UseDevReturn } from './useDev.types';

export function useDev(): UseDevReturn {
    const { data, isLoading } = useStreamGithubStateQuery();
    return {
        liveData: data ?? null,
        loading: isLoading,
        mockData: devMock,
    };
}
