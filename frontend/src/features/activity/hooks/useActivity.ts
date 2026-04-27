import { useAppSelector } from '@app';
import { useStreamActivityQuery } from '../activityApi';
import {
    selectActivityState,
    selectQuietUntil,
    selectActivitySources,
    selectActivityHistory,
    selectActivityHasLiveData,
} from '../activitySelectors';
import type { UseActivityReturn } from './useActivity.types';

export function useActivity(): UseActivityReturn {
    useStreamActivityQuery();

    const engineState = useAppSelector(selectActivityState);
    const quietUntil = useAppSelector(selectQuietUntil);
    const sources = useAppSelector(selectActivitySources);
    const history = useAppSelector(selectActivityHistory);
    const hasLiveData = useAppSelector(selectActivityHasLiveData);

    return { engineState, quietUntil, sources, history, hasLiveData };
}
