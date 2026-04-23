import type { ReactElement } from 'react';
import { StoreProvider } from './StoreProvider';
import { WebSocketProvider } from './WebSocketProvider';
import { PanelAvailabilityProvider } from './PanelAvailabilityProvider';
import type { AppProvidersProps } from './AppProviders.types';

/**
 * Composes all app-level providers.
 *
 * Order (outer → inner):
 *   StoreProvider — Redux store, must wrap all RTK Query consumers.
 *   WebSocketProvider — connects singleton wsClient on mount.
 *   PanelAvailabilityProvider — panel reachability context.
 *
 * SfxProvider is instantiated inside AppShell (needs orbState from the store)
 * rather than here.
 */
export function AppProviders({ children }: AppProvidersProps): ReactElement {
    return (
        <StoreProvider>
            <WebSocketProvider>
                <PanelAvailabilityProvider>
                    {children}
                </PanelAvailabilityProvider>
            </WebSocketProvider>
        </StoreProvider>
    );
}

export default AppProviders;
