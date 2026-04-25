import { baseApi } from '@core/api/baseApi';
import { wsClient } from '@core/websocket/wsClient';
import { systemMetricsReceived } from './systemSlice';
import type { SystemMetricsPayload } from './types';

export const systemApi = baseApi.injectEndpoints({
    endpoints: (builder) => ({
        streamSystem: builder.query<null, void>({
            queryFn: () => ({ data: null }),
            async onCacheEntryAdded(_arg, { cacheDataLoaded, cacheEntryRemoved, dispatch }) {
                await cacheDataLoaded;

                const unsub = wsClient.subscribe<{ type: string; payload: SystemMetricsPayload }>(
                    'system',
                    (msg) => dispatch(systemMetricsReceived(msg.payload)),
                );

                await cacheEntryRemoved;
                unsub();
            },
        }),
    }),
});

export const { useStreamSystemQuery } = systemApi;
