import { useContext } from 'react';
import type { PanelAvailabilityContextValue } from './PanelAvailabilityProvider.types';
import { PanelAvailabilityContext } from './PanelAvailabilityContext';

export function usePanelAvailabilityContext(): PanelAvailabilityContextValue {
    const ctx = useContext(PanelAvailabilityContext);
    if (!ctx) {
        throw new Error('usePanelAvailable must be used inside <PanelAvailabilityProvider>');
    }
    return ctx;
}
