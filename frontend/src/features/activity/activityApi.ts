import { baseApi } from '@core/api/baseApi';
import { wsClient } from '@core/websocket/wsClient';
import { narrationStateReceived, activityPanelReceived } from './activitySlice';
import type { NarrationStatePayload, ActivityPanelPayload } from './types';

export const activityApi = baseApi.injectEndpoints({
    endpoints: (builder) => ({
        streamActivity: builder.query<null, void>({
            queryFn: () => ({ data: null }),
            async onCacheEntryAdded(_arg, { cacheDataLoaded, cacheEntryRemoved, dispatch }) {
                await cacheDataLoaded;

                const unsubNarration = wsClient.subscribe<{ type: string; payload: NarrationStatePayload }>(
                    'narration_state',
                    (msg) => dispatch(narrationStateReceived(msg.payload)),
                );

                const unsubActivity = wsClient.subscribe<{ type: string; payload: ActivityPanelPayload }>(
                    'activity_panel',
                    (msg) => dispatch(activityPanelReceived(msg.payload)),
                );

                await cacheEntryRemoved;
                unsubNarration();
                unsubActivity();
            },
        }),
    }),
});

export const { useStreamActivityQuery } = activityApi;
