/**
 * settingsApi — RTK Query endpoints for settings-related backend calls.
 *
 * Endpoints:
 *   getRepos   GET  /api/config/repos
 *   saveRepos  POST /api/config/repos
 */
import { baseApi } from '@core/api/baseApi';
import type { ReposConfig } from './types';

export const settingsApi = baseApi.injectEndpoints({
    endpoints: (builder) => ({
        getRepos: builder.query<ReposConfig, void>({
            query: () => '/api/config/repos',
            providesTags: ['repos'],
        }),
        saveRepos: builder.mutation<ReposConfig, ReposConfig>({
            query: (body) => ({
                url: '/api/config/repos',
                method: 'POST',
                body,
            }),
            invalidatesTags: ['repos'],
        }),
    }),
    overrideExisting: false,
});

export const { useGetReposQuery, useSaveReposMutation } = settingsApi;
