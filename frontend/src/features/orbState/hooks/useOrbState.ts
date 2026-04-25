import { useAppSelector } from '@app/hooks';
import { useStreamOrbStateQuery } from '../orbStateApi';
import { selectAppOrbState, selectConnected } from '../orbStateSelectors';
import type { UseOrbStateReturn } from './useOrbState.types';

/**
 * Subscribes to the orbState streaming query and returns the derived
 * AppOrbState + connection flag for App.tsx to consume.
 */
export function useOrbState(): UseOrbStateReturn {
    useStreamOrbStateQuery();
    return {
        state: useAppSelector(selectAppOrbState),
        connected: useAppSelector(selectConnected),
    };
}
