/**
 * PanelAvailabilityProvider — lightweight context panels use to report whether
 * their backend data source is reachable.
 *
 * Moved from src/contexts/PanelAvailability.tsx to src/app/providers/.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import type { ReactElement } from 'react';
import type { PanelId } from '@common/types';
import type {
    AvailabilityMap,
    PanelAvailabilityContextValue,
    PanelAvailabilityProviderProps,
} from './PanelAvailabilityProvider.types';
import { PanelAvailabilityContext } from './PanelAvailabilityContext';
import { usePanelAvailabilityContext } from './usePanelAvailabilityContext';

export function PanelAvailabilityProvider({
    children,
}: PanelAvailabilityProviderProps): ReactElement {
    const [availability, setAvailability] = useState<AvailabilityMap>({});

    const report = useCallback((id: PanelId, available: boolean): void => {
        setAvailability((prev) => {
            if (prev[id] === available) return prev;
            return { ...prev, [id]: available };
        });
    }, []);

    const value = useMemo<PanelAvailabilityContextValue>(
        () => ({ availability, report }),
        [availability, report],
    );

    return (
        <PanelAvailabilityContext.Provider value={value}>
            {children}
        </PanelAvailabilityContext.Provider>
    );
}

export function usePanelAvailable(id: PanelId, available: boolean): void {
    const { report } = usePanelAvailabilityContext();
    useEffect(() => {
        report(id, available);
    }, [id, available, report]);
}

export function useAvailabilityMap(): AvailabilityMap {
    const { availability } = usePanelAvailabilityContext();
    return availability;
}

export function isPanelAvailable(map: AvailabilityMap, id: PanelId): boolean {
    const v = map[id];
    return v === undefined || v === true;
}

export default PanelAvailabilityProvider;
