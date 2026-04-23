import { baseApi } from '@core/api/baseApi';
import { wsClient } from '@core/websocket/wsClient';
import { transcriptReceived } from './transcriptSlice';
import type { TranscriptPayload } from './types';

export const transcriptApi = baseApi.injectEndpoints({
    endpoints: (builder) => ({
        streamTranscript: builder.query<null, void>({
            queryFn: () => ({ data: null }),
            async onCacheEntryAdded(_arg, { cacheDataLoaded, cacheEntryRemoved, dispatch }) {
                await cacheDataLoaded;

                const unsub = wsClient.subscribe<{ type: string; payload: TranscriptPayload }>(
                    'transcript',
                    (msg) => dispatch(transcriptReceived(msg.payload)),
                );

                await cacheEntryRemoved;
                unsub();
            },
        }),
    }),
});

export const { useStreamTranscriptQuery } = transcriptApi;
