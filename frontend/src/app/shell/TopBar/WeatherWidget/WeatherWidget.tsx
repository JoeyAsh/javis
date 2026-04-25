/**
 * WeatherWidget — fetches current conditions from Open-Meteo (no API key required).
 *
 * Uses RTK Query's weatherApi instead of direct fetch().
 * Renders temperature + WMO weather-code icon; marks stale on error.
 */

import type { ReactElement } from 'react';
import { useGetWeatherQuery } from '@core/api/weatherApi';
import type { WeatherWidgetProps } from './WeatherWidget.types';
import { wmoToIcon } from './utils';

export function WeatherWidget({ latitude, longitude }: WeatherWidgetProps): ReactElement {
    const { data, isError } = useGetWeatherQuery({ latitude, longitude });

    const temperature =
        data?.current?.temperature_2m !== undefined
            ? Math.round(data.current.temperature_2m)
            : null;
    const icon =
        data?.current?.weather_code !== undefined
            ? wmoToIcon(data.current.weather_code)
            : '·';
    const tempLabel = temperature === null ? '—°C' : `${temperature}°C`;

    return (
        <span
            className={['text-text-secondary', isError ? 'opacity-40' : ''].filter(Boolean).join(' ')}
            aria-label="Current weather"
        >
            <span className="mr-1" aria-hidden="true">{icon}</span>
            {tempLabel}
        </span>
    );
}

export default WeatherWidget;
