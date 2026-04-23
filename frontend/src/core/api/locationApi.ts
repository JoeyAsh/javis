import { baseApi } from './baseApi';
import type { LocationCoords } from '@common/types/location';

export const locationApi = baseApi.injectEndpoints({
    endpoints: (builder) => ({
        getLocation: builder.query<LocationCoords, void>({
            query: () => '/api/config/location',
        }),
    }),
});

export const { useGetLocationQuery } = locationApi;
