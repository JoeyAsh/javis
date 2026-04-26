import { baseApi } from '@core/api/baseApi';
import { wsClient } from '@core/websocket/wsClient';
import { deviceInfoReceived } from './deviceSlice';
import type { DeviceInfoPayload } from './types';

export const deviceApi = baseApi.injectEndpoints({
    endpoints: (builder) => ({
        streamDeviceInfo: builder.query<null, void>({
            queryFn: () => ({ data: null }),
            async onCacheEntryAdded(
                _arg,
                { cacheDataLoaded, cacheEntryRemoved, dispatch },
            ) {
                await cacheDataLoaded;

                const unsub = wsClient.subscribe<{ type: string; payload: DeviceInfoPayload }>(
                    'device_info',
                    (msg) => dispatch(deviceInfoReceived(msg.payload)),
                );

                await cacheEntryRemoved;
                unsub();
            },
        }),
    }),
});

export const { useStreamDeviceInfoQuery } = deviceApi;
