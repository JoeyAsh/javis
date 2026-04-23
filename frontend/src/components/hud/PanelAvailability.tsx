/**
ich hab * Legacy re-export — all PanelAvailability logic has moved to
 * src/contexts/PanelAvailability.tsx. This file re-exports everything
 * so existing panel imports continue to work during migration.
 */
export {
    PanelAvailabilityProvider,
    usePanelAvailable,
    useAvailabilityMap,
    isPanelAvailable,
} from '../../contexts/PanelAvailability';
export type { PanelAvailabilityProviderProps } from '../../contexts/PanelAvailability';
