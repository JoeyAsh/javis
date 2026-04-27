import { baseApi } from '@core/api/baseApi';
import { wsClient } from '@core/websocket/wsClient';
import { brainInspectorReceived } from './brainSlice';
import type { BrainInspectorPayload, LedgerQueryRequest } from './types';

export const brainApi = baseApi.injectEndpoints({
    endpoints: (builder) => ({
        streamBrainInspector: builder.query<null, void>({
            queryFn: () => ({ data: null }),
            async onCacheEntryAdded(_arg, { cacheDataLoaded, cacheEntryRemoved, dispatch }) {
                await cacheDataLoaded;

                const unsubscribe = wsClient.subscribe<{
                    type: string;
                    payload: BrainInspectorPayload;
                }>('brain_inspector', (msg) => dispatch(brainInspectorReceived(msg.payload)));

                await cacheEntryRemoved;
                unsubscribe();
            },
        }),
    }),
});

export const { useStreamBrainInspectorQuery } = brainApi;

/**
 * Send a `ledger_query` command to the backend via the singleton WS client.
 * The backend replies with a `brain_inspector` message on the same stream.
 */
export function sendLedgerQuery(request: LedgerQueryRequest): void {
    wsClient.send({ type: 'ledger_query', payload: request });
}
