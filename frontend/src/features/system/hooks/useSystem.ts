import { useAppSelector } from '@app';
import { useStreamSystemQuery } from '../systemApi';
import {
    selectSystemLive,
    selectSystemHistories,
    selectSystemHasLiveData,
} from '../systemSelectors';
import type { UseSystemReturn } from './useSystem.types';

export function useSystem(): UseSystemReturn {
    const { isLoading } = useStreamSystemQuery();

    const live = useAppSelector(selectSystemLive);
    const histories = useAppSelector(selectSystemHistories);
    const hasLiveData = useAppSelector(selectSystemHasLiveData);

    return { live, histories, hasLiveData, loading: isLoading };
}
