import { useEffect, type ReactElement } from 'react';
import { wsClient } from '@core/websocket/wsClient';
import type { WebSocketProviderProps } from './WebSocketProvider.types';

const DEFAULT_URL = '/jarvis-ws';

/**
 * Connects the singleton WsClient on mount and disconnects on unmount.
 * Must be mounted inside <StoreProvider> so dispatched actions land in the store.
 */
export function WebSocketProvider({
    children,
    url = DEFAULT_URL,
}: WebSocketProviderProps): ReactElement {
    useEffect(() => {
        // Singleton WS — connect is idempotent. We deliberately do NOT
        // disconnect on unmount: under React 18 StrictMode the cleanup
        // fires during the dev double-mount and was racing the still-
        // CONNECTING socket, producing "closed before established" errors
        // and the backend "Cannot write to closing transport" warnings.
        // The socket lives for the lifetime of the tab; the browser will
        // close it on tab-close, which is sufficient.
        wsClient.connect(url);
    }, [url]);

    return <>{children}</>;
}

export default WebSocketProvider;
