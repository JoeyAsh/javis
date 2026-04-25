import { baseApi } from '@core/api/baseApi';
import { wsClient } from '@core/websocket/wsClient';
import { logLineReceived, turnTimingReceived } from './logSlice';
import type { LogLinePayload, TurnTimingPayload } from './types';

export const logApi = baseApi.injectEndpoints({
    endpoints: (builder) => ({
        streamLog: builder.query<null, void>({
            queryFn: () => ({ data: null }),
            async onCacheEntryAdded(_arg, { cacheDataLoaded, cacheEntryRemoved, dispatch }) {
                await cacheDataLoaded;

                const unsubs = [
                    wsClient.subscribe<{ type: string; payload: LogLinePayload }>(
                        'log_line',
                        (msg) => dispatch(logLineReceived(msg.payload)),
                    ),
                    wsClient.subscribe<{ type: string; payload: TurnTimingPayload }>(
                        'turn_timing',
                        (msg) => dispatch(turnTimingReceived(msg.payload)),
                    ),
                ];

                await cacheEntryRemoved;
                unsubs.forEach((u) => u());
            },
        }),
    }),
});

export const { useStreamLogQuery } = logApi;
