import { useEffect } from 'react';
import { useAppDispatch } from '@app/hooks';
import { briefingCleared } from '../briefingSlice';

const FOUR_HOURS_MS = 4 * 60 * 60 * 1000;

/**
 * Dispatches `briefingCleared` once 4 hours have elapsed since `receivedAt`.
 * Resets the timer whenever `receivedAt` changes.
 */
export function useBriefingAutoClear(receivedAt: string | null): void {
    const dispatch = useAppDispatch();

    useEffect(() => {
        if (receivedAt === null) return;

        const elapsed = Date.now() - new Date(receivedAt).getTime();
        const remaining = FOUR_HOURS_MS - elapsed;

        if (remaining <= 0) {
            dispatch(briefingCleared());
            return;
        }

        const timerId = setTimeout(() => {
            dispatch(briefingCleared());
        }, remaining);

        return () => {
            clearTimeout(timerId);
        };
    }, [receivedAt, dispatch]);
}
