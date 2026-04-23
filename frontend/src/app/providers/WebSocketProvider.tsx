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
        wsClient.connect(url);
        return () => {
            wsClient.disconnect();
        };
    }, [url]);

    return <>{children}</>;
}

export default WebSocketProvider;
