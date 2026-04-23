/**
 * @deprecated Import from '@app/providers/PanelAvailabilityProvider' instead.
 *
 * Re-export shim so legacy relative imports continue to resolve while
 * consumers migrate to the canonical provider location.
 */

export {
    PanelAvailabilityProvider,
    usePanelAvailable,
    useAvailabilityMap,
    isPanelAvailable,
} from '../app/providers/PanelAvailabilityProvider';
export type {
    PanelAvailabilityProviderProps,
    AvailabilityMap,
} from '../app/providers/PanelAvailabilityProvider';
