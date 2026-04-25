import { baseApi } from '@core/api/baseApi';
import { wsClient } from '@core/websocket/wsClient';
import { gitlabStateReceived } from './gitlabSlice';
import type { GitLabStatePayload } from './types';

export const gitlabApi = baseApi.injectEndpoints({
    endpoints: (builder) => ({
        streamGitlabState: builder.query<null, void>({
            queryFn: () => ({ data: null }),
            async onCacheEntryAdded(
                _arg,
                { cacheDataLoaded, cacheEntryRemoved, dispatch },
            ) {
                await cacheDataLoaded;

                const unsub = wsClient.subscribe<{ type: string; payload: GitLabStatePayload }>(
                    'gitlab_state',
                    (msg) => dispatch(gitlabStateReceived(msg.payload)),
                );

                await cacheEntryRemoved;
                unsub();
            },
        }),
    }),
});

export const { useStreamGitlabStateQuery } = gitlabApi;
