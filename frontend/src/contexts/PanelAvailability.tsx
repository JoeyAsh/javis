/**
 * PanelAvailability — lightweight context that panels use to report whether
 * their backend data source is reachable.
 *
 * Migrated from components/hud/PanelAvailability.tsx to src/contexts/ so it
 * can live independently of the legacy component tree.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactElement, ReactNode } from 'react';
import type { PanelId } from '../types';

type AvailabilityMap = Partial<Record<PanelId, boolean>>;

interface PanelAvailabilityValue {
    availability: AvailabilityMap;
    report: (id: PanelId, available: boolean) => void;
}

const PanelAvailabilityContext = createContext<PanelAvailabilityValue | null>(null);

export interface PanelAvailabilityProviderProps {
    children: ReactNode;
}

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

    const value = useMemo<PanelAvailabilityValue>(
        () => ({ availability, report }),
        [availability, report],
    );

    return (
        <PanelAvailabilityContext.Provider value={value}>
            {children}
        </PanelAvailabilityContext.Provider>
    );
}

function usePanelAvailabilityContext(): PanelAvailabilityValue {
    const ctx = useContext(PanelAvailabilityContext);
    if (!ctx) {
        throw new Error('usePanelAvailable must be used inside <PanelAvailabilityProvider>');
    }
    return ctx;
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

