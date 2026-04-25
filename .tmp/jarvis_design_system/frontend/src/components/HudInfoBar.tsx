import { useEffect, useRef, useState } from 'react';
import type { ReactElement } from 'react';

/**
 * Response shape for the Open-Meteo `current_weather` endpoint subset we care
 * about. Only the fields we actually read are typed.
 */
interface OpenMeteoCurrentWeather {
  temperature: number;
  weathercode: number;
}

interface OpenMeteoResponse {
  current_weather?: OpenMeteoCurrentWeather;
}

interface WeatherState {
  /** Integer degrees Celsius, rounded. `null` while we have never loaded. */
  temperature: number | null;
  /** Single-glyph icon reflecting current conditions. */
  icon: string;
}

export interface HudInfoBarProps {
  /**
   * City label shown next to the temperature. Defaults to `Wien`.
   * Latitude / longitude are fixed to Wien for MVP; made configurable when
   * the backend starts serving user location.
   */
  city?: string;
}

const LOCALE = 'de-DE';
const TIMEZONE = 'Europe/Berlin';
const WEATHER_URL =
  'https://api.open-meteo.com/v1/forecast?latitude=48.2082&longitude=16.3738&current_weather=true&timezone=Europe%2FVienna';
const TIME_TICK_MS = 1_000;
const WEATHER_TICK_MS = 15 * 60 * 1000;

const TIME_FORMATTER = new Intl.DateTimeFormat(LOCALE, {
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hour12: false,
  timeZone: TIMEZONE,
});

const DATE_FORMATTER = new Intl.DateTimeFormat(LOCALE, {
  weekday: 'long',
  day: 'numeric',
  month: 'long',
  year: 'numeric',
  timeZone: TIMEZONE,
});

/**
 * Maps an Open-Meteo WMO weathercode to a glyph icon. Keep in sync with the
 * mapping documented in the design spec.
 */
function weatherCodeToIcon(code: number): string {
  if (code === 0) return '☀';
  if (code === 1 || code === 2 || code === 3) return '☁';
  if (code === 45 || code === 48) return '🌫';
  if (code >= 51 && code <= 67) return '🌧';
  if (code >= 71 && code <= 77) return '❄';
  if (code >= 80 && code <= 82) return '🌧';
  if (code === 85 || code === 86) return '❄';
  if (code >= 95 && code <= 99) return '⛈';
  return '·';
}

/**
 * Left-aligned HUD top-bar cluster showing time, date, and current weather.
 * All text is German (de-DE, Europe/Berlin). Weather comes from Open-Meteo
 * (no API key). Updates: time every 10 s, date on mount + at midnight,
 * weather every 15 min. Graceful degradation if the weather fetch fails.
 */
export function HudInfoBar({ city = 'Wien' }: HudInfoBarProps): ReactElement {
  const [now, setNow] = useState<Date>(() => new Date());
  const [weather, setWeather] = useState<WeatherState>({
    temperature: null,
    icon: '·',
  });

  // Tick the clock every 10 s. We also rely on this re-render to pick up the
  // new date label whenever the day rolls over past midnight.
  useEffect(() => {
    const id = window.setInterval(() => {
      setNow(new Date());
    }, TIME_TICK_MS);
    return () => {
      window.clearInterval(id);
    };
  }, []);

  // Fetch weather on mount + every 15 min. Uses AbortController so we don't
  // leak pending requests across unmounts. Failures are swallowed: we keep
  // whatever state we had. On the very first failure the placeholder "—°C"
  // remains (temperature === null).
  const controllerRef = useRef<AbortController | null>(null);
  useEffect(() => {
    let cancelled = false;

    const load = async (): Promise<void> => {
      controllerRef.current?.abort();
      const controller = new AbortController();
      controllerRef.current = controller;
      try {
        const res = await fetch(WEATHER_URL, { signal: controller.signal });
        if (!res.ok) return;
        const data = (await res.json()) as OpenMeteoResponse;
        const current = data.current_weather;
        if (!current || cancelled) return;
        setWeather({
          temperature: Math.round(current.temperature),
          icon: weatherCodeToIcon(current.weathercode),
        });
      } catch {
        // Network / abort / parse failure: silent. Keep last-known state.
      }
    };

    void load();
    const id = window.setInterval(() => {
      void load();
    }, WEATHER_TICK_MS);

    return () => {
      cancelled = true;
      window.clearInterval(id);
      controllerRef.current?.abort();
      controllerRef.current = null;
    };
  }, []);

  const timeLabel = TIME_FORMATTER.format(now);
  const dateLabel = DATE_FORMATTER.format(now);
  const tempLabel =
    weather.temperature === null ? '— °C' : `${weather.temperature}°C`;

  return (
    <div className="hud-infobar" aria-label="Zeit, Datum und Wetter">
      <span className="hud-infobar__time">{timeLabel}</span>
      <span className="hud-infobar__sep" aria-hidden="true">
        ·
      </span>
      <span className="hud-infobar__date">{dateLabel}</span>
      <span className="hud-infobar__sep" aria-hidden="true">
        ·
      </span>
      <span className="hud-infobar__weather">
        <span className="hud-infobar__weather-icon" aria-hidden="true">
          {weather.icon}
        </span>
        {tempLabel} {city}
      </span>
    </div>
  );
}

export default HudInfoBar;
