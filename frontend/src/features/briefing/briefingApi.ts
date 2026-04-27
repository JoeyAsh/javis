import { baseApi } from '@core/api/baseApi';
import { wsClient } from '@core/websocket/wsClient';
import { briefingReceived } from './briefingSlice';
import type { BriefingStatePayload } from './types';

export const briefingApi = baseApi.injectEndpoints({
    endpoints: (builder) => ({
        streamBriefing: builder.query<null, void>({
            queryFn: () => ({ data: null }),
            async onCacheEntryAdded(_arg, { cacheDataLoaded, cacheEntryRemoved, dispatch }) {
                await cacheDataLoaded;

                const unsub = wsClient.subscribe<{ type: string; payload: BriefingStatePayload }>(
                    'morning_briefing',
                    (msg) => dispatch(briefingReceived(msg.payload)),
                );

                await cacheEntryRemoved;
                unsub();
            },
        }),
    }),
});

export const { useStreamBriefingQuery } = briefingApi;
