import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';
import { getApiToken } from './tokenStore';

const baseQuery = fetchBaseQuery({
    baseUrl: '/',
    prepareHeaders: (headers) => {
        const token = getApiToken();
        if (token) {
            headers.set('Authorization', `Bearer ${token}`);
        }
        return headers;
    },
});

export const baseApi = createApi({
    reducerPath: 'api',
    baseQuery,
    tagTypes: ['repos', 'queue'],
    endpoints: () => ({}),
});
