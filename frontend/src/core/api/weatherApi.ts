/**
 * RTK Query endpoint for Open-Meteo weather data.
 *
 * Open-Meteo is a free weather API that requires no API key.
 * The base URL is absolute (external domain) — the Vite proxy is not involved.
 * fetchBaseQuery with an absolute URL is the correct approach here.
 */

import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';

const WEATHER_POLL_MS = 15 * 60 * 1000; // 15 minutes

export interface WeatherQueryArg {
    latitude: number;
    longitude: number;
}

export interface OpenMeteoResponse {
    current?: {
        temperature_2m?: number;
        weather_code?: number;
    };
}

export const weatherApi = createApi({
    reducerPath: 'weatherApi',
    baseQuery: fetchBaseQuery({
        baseUrl: 'https://api.open-meteo.com/v1/',
    }),
    endpoints: (builder) => ({
        getWeather: builder.query<OpenMeteoResponse, WeatherQueryArg>({
            query: ({ latitude, longitude }) =>
                `forecast?latitude=${latitude.toFixed(4)}&longitude=${longitude.toFixed(4)}&current=temperature_2m,weather_code&timezone=auto`,
            // Refetch on focus to keep weather reasonably current
            keepUnusedDataFor: WEATHER_POLL_MS / 1000,
        }),
    }),
});

export const { useGetWeatherQuery } = weatherApi;
