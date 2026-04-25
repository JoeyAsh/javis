import { baseApi } from './baseApi';
import { wsClient } from '@core/websocket/wsClient';
import type { GitHubStatePayload } from '@core/websocket/types';

export const githubApi = baseApi.injectEndpoints({
    endpoints: (builder) => ({
        streamGithubState: builder.query<GitHubStatePayload | null, void>({
            queryFn: () => ({ data: null }),
            async onCacheEntryAdded(
                _arg,
                { cacheDataLoaded, cacheEntryRemoved, updateCachedData },
            ) {
                await cacheDataLoaded;

                const unsub = wsClient.subscribe<{ payload: GitHubStatePayload }>(
                    'github_state',
                    (msg) => updateCachedData(() => msg.payload),
                );

                await cacheEntryRemoved;
                unsub();
            },
        }),
    }),
});

export const { useStreamGithubStateQuery } = githubApi;
