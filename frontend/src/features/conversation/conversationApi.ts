import { baseApi } from '@core/api/baseApi';
import { wsClient } from '@core/websocket/wsClient';
import { conversationModeReceived } from './conversationSlice';
import type { ConversationModePayload } from './types';

interface ConversationModeMessage {
    type: string;
    payload: ConversationModePayload;
}

export const conversationApi = baseApi.injectEndpoints({
    endpoints: (builder) => ({
        streamConversationMode: builder.query<null, void>({
            queryFn: () => ({ data: null }),
            async onCacheEntryAdded(
                _arg,
                { cacheDataLoaded, cacheEntryRemoved, dispatch },
            ) {
                await cacheDataLoaded;

                const unsub = wsClient.subscribe<ConversationModeMessage>(
                    'conversation_mode',
                    (msg) =>
                        dispatch(
                            conversationModeReceived({
                                active: msg.payload.active,
                                seconds_remaining: msg.payload.seconds_remaining,
                            }),
                        ),
                );

                await cacheEntryRemoved;
                unsub();
            },
        }),
    }),
});

export const { useStreamConversationModeQuery } = conversationApi;
