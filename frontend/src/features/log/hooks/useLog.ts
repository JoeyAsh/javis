import { useCallback } from 'react';
import { useAppSelector, useAppDispatch } from '@app';
import { useStreamLogQuery } from '../logApi';
import { logCleared } from '../logSlice';
import { selectLogLines, selectTurnTimings } from '../logSelectors';
import type { UseLogReturn } from './useLog.types';

export function useLog(): UseLogReturn {
    const dispatch = useAppDispatch();
    const { isLoading } = useStreamLogQuery();

    const lines = useAppSelector(selectLogLines);
    const turnTimings = useAppSelector(selectTurnTimings);

    const clear = useCallback((): void => {
        dispatch(logCleared());
    }, [dispatch]);

    return { lines, turnTimings, loading: isLoading, clear };
}
