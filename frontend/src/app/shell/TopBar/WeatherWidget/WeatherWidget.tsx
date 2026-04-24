/**
 * WeatherWidget — fetches current conditions from Open-Meteo (no API key required).
 *
 * Uses RTK Query's weatherApi instead of direct fetch().
 * Renders temperature + WMO weather-code icon; marks stale on error.
 */

import type { ReactElement } from 'react';
import { useGetWeatherQuery } from '@core/api/weatherApi';
import type { WeatherWidgetProps } from './WeatherWidget.types';

function wmoToIcon(code: number): string {
    if (code === 0) return '☀';
    if (code <= 3) return '☁';
    if (code === 45 || code === 48) return '🌫';
    if (code >= 51 && code <= 67) return '🌧';
    if (code >= 71 && code <= 77) return '❄';
    if (code >= 80 && code <= 82) return '🌧';
    if (code === 85 || code === 86) return '❄';
    if (code >= 95) return '⛈';
    return '·';
}

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
