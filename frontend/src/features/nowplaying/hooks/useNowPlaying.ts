import { useAppSelector } from '@app';
import { useStreamNowplayingQuery } from '../nowplayingApi';
import { selectNowPlayingPayload, selectNowPlayingHasLiveData } from '../nowplayingSelectors';
import type { UseNowPlayingReturn } from './useNowPlaying.types';

export function useNowPlaying(): UseNowPlayingReturn {
    const { isLoading } = useStreamNowplayingQuery();
    const payload = useAppSelector(selectNowPlayingPayload);
    const hasLiveData = useAppSelector(selectNowPlayingHasLiveData);

    return { payload, hasLiveData, loading: isLoading };
}
