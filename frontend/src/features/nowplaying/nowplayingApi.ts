import { baseApi } from '@core/api/baseApi';
import { wsClient } from '@core/websocket/wsClient';
import { spotifyStateReceived } from './nowplayingSlice';
import type { SpotifyStatePayload, SpotifyCmdAction } from './types';

export const nowplayingApi = baseApi.injectEndpoints({
    endpoints: (builder) => ({
        streamNowplaying: builder.query<null, void>({
            queryFn: () => ({ data: null }),
            async onCacheEntryAdded(_arg, { cacheDataLoaded, cacheEntryRemoved, dispatch }) {
                await cacheDataLoaded;

                const unsub = wsClient.subscribe<{ type: string; payload: SpotifyStatePayload }>(
                    'spotify_state',
                    (msg) => dispatch(spotifyStateReceived(msg.payload)),
                );

                await cacheEntryRemoved;
                unsub();
            },
        }),
    }),
});

export const { useStreamNowplayingQuery } = nowplayingApi;

/**
 * One-way command helper — sends a Spotify transport command without waiting
 * for a server acknowledgement. No Redux involvement.
 */
export function sendSpotifyCmd(action: SpotifyCmdAction, value?: number): void {
    wsClient.send({ type: 'spotify_cmd', payload: { action, value } });
}
