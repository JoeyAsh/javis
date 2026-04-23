import { baseApi } from '@core/api/baseApi';
import { wsClient } from '@core/websocket/wsClient';
import { notificationReceived } from './notificationsSlice';
import type { NotificationPayload } from './types';

export const notificationsApi = baseApi.injectEndpoints({
    endpoints: (builder) => ({
        streamNotifications: builder.query<null, void>({
            queryFn: () => ({ data: null }),
            async onCacheEntryAdded(_arg, { cacheDataLoaded, cacheEntryRemoved, dispatch }) {
                await cacheDataLoaded;

                const unsub = wsClient.subscribe<{ type: string; payload: NotificationPayload }>(
                    'notification',
                    (msg) => dispatch(notificationReceived(msg.payload)),
                );

                await cacheEntryRemoved;
                unsub();
            },
        }),
    }),
});

export const { useStreamNotificationsQuery } = notificationsApi;
