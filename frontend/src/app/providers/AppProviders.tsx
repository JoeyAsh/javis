import type { ReactElement } from 'react';
import { StoreProvider } from './StoreProvider';
import { WebSocketProvider } from './WebSocketProvider';
import type { AppProvidersProps } from './AppProviders.types';

/**
 * Composes all app-level providers.
 * Order: StoreProvider wraps WebSocketProvider so WS subscribers can dispatch.
 * Future: SfxProvider, PanelAvailabilityProvider will join here in later batches.
 */
export function AppProviders({ children }: AppProvidersProps): ReactElement {
    return (
        <StoreProvider>
            <WebSocketProvider>{children}</WebSocketProvider>
        </StoreProvider>
    );
}

export default AppProviders;
