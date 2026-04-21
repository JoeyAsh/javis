/**
 * HudTopBar — Hypermodern top app-bar for JARVIS.
 *
 * Shell: position:fixed; top/left/right:10px; height:40px;
 *   glass: rgba(13,13,20,.55) + blur(14px); hairline border; 2px radius.
 * Primitives: HudCornerBrackets (tbCornerBreath staggered), HudLightTrace
 *   (topbar-specific 5.2s timings set in hud.css).
 *
 * Content left→right:
 *   LINK·SECURE pulsing dot · Clock (HH:MM:SS de-DE tabular) · Long date ·
 *   Weather (Open-Meteo) · Coords · ── CENTER BRAND ── · Icon cluster (4 btns)
 *
 * Props:
 *   idle, onToggleIdle, onResetLayout, onOpenSettings (preserved)
 *   tweaksOpen, onToggleTweaks (new)
 */

import { useEffect, useRef, useState } from 'react';
import type { ReactElement } from 'react';
import { HudCornerBrackets } from './hud/primitives/HudCornerBrackets';
import { HudLightTrace } from './hud/primitives/HudLightTrace';
import { HudIconButton } from './hud/primitives/HudIconButton';
import { useLocation } from '../hooks/useLocation';
import './HudTopBar.css';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const LOCALE = 'de-DE';
const TZ = 'Europe/Berlin';
const TIME_TICK_MS = 1_000;
const WEATHER_TICK_MS = 15 * 60 * 1_000;

const TIME_FMT = new Intl.DateTimeFormat(LOCALE, {
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hour12: false,
  timeZone: TZ,
});

const DATE_FMT = new Intl.DateTimeFormat(LOCALE, {
  weekday: 'long',
  day: 'numeric',
  month: 'long',
  year: 'numeric',
  timeZone: TZ,
});

// ---------------------------------------------------------------------------
// Weather helpers
// ---------------------------------------------------------------------------

interface WeatherState {
  temperature: number | null;
  icon: string;
  stale: boolean;
}

interface OpenMeteoResponse {
  current?: {
    temperature_2m?: number;
    weather_code?: number;
  };
}

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

function buildWeatherUrl(lat: number, lon: number): string {
  return (
    `https://api.open-meteo.com/v1/forecast` +
    `?latitude=${lat.toFixed(4)}&longitude=${lon.toFixed(4)}` +
    `&current=temperature_2m,weather_code&timezone=auto`
  );
}

// ---------------------------------------------------------------------------
// WeatherWidget — isolated so it re-renders on coord change
// ---------------------------------------------------------------------------

interface WeatherWidgetProps {
  latitude: number;
  longitude: number;
}

function WeatherWidget({ latitude, longitude }: WeatherWidgetProps): ReactElement {
  const [weather, setWeather] = useState<WeatherState>({
    temperature: null,
    icon: '·',
    stale: false,
  });
  const controllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    let cancelled = false;

    const load = async (): Promise<void> => {
      controllerRef.current?.abort();
      const controller = new AbortController();
      controllerRef.current = controller;
      try {
        const res = await fetch(buildWeatherUrl(latitude, longitude), {
          signal: controller.signal,
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = (await res.json()) as OpenMeteoResponse;
        const cur = data.current;
        if (!cur || cancelled) return;
        setWeather({
          temperature: cur.temperature_2m !== undefined ? Math.round(cur.temperature_2m) : null,
          icon: cur.weather_code !== undefined ? wmoToIcon(cur.weather_code) : '·',
          stale: false,
        });
      } catch {
        if (!cancelled) {
          setWeather((prev) => ({ ...prev, stale: true }));
        }
      }
    };

    void load();
    const id = window.setInterval(() => { void load(); }, WEATHER_TICK_MS);

    return () => {
      cancelled = true;
      window.clearInterval(id);
      controllerRef.current?.abort();
      controllerRef.current = null;
    };
  }, [latitude, longitude]);

  const tempLabel = weather.temperature === null ? '—°C' : `${weather.temperature}°C`;

  return (
    <span
      className={`hud-topbar__weather${weather.stale ? ' hud-topbar__weather--stale' : ''}`}
      aria-label="Current weather"
    >
      <span aria-hidden="true">{weather.icon}</span>
      {' '}{tempLabel}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Icon SVGs
// ---------------------------------------------------------------------------

function IdleIcon(): ReactElement {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <line x1="10" y1="15" x2="10" y2="9" />
      <line x1="14" y1="15" x2="14" y2="9" />
    </svg>
  );
}

function ResetIcon(): ReactElement {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 12a9 9 0 1 0 3-6.7" />
      <path d="M3 4v5h5" />
    </svg>
  );
}

function TweaksIcon(): ReactElement {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <line x1="4" y1="6" x2="20" y2="6" />
      <line x1="4" y1="12" x2="20" y2="12" />
      <line x1="4" y1="18" x2="20" y2="18" />
      <circle cx="8" cy="6" r="2" fill="currentColor" />
      <circle cx="16" cy="12" r="2" fill="currentColor" />
      <circle cx="10" cy="18" r="2" fill="currentColor" />
    </svg>
  );
}

function SettingsIcon(): ReactElement {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.6-1.1 1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.9.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface HudTopBarProps {
  idle: boolean;
  onToggleIdle: () => void;
  onResetLayout: () => void;
  onOpenSettings: () => void;
  tweaksOpen?: boolean;
  onToggleTweaks?: () => void;
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function HudTopBar({
  idle,
  onToggleIdle,
  onResetLayout,
  onOpenSettings,
  tweaksOpen = false,
  onToggleTweaks,
}: HudTopBarProps): ReactElement {
  const [now, setNow] = useState<Date>(() => new Date());
  const location = useLocation();

  // Tick clock every second
  useEffect(() => {
    const id = window.setInterval(() => {
      setNow(new Date());
    }, TIME_TICK_MS);
    return () => { window.clearInterval(id); };
  }, []);

  const timeLabel = TIME_FMT.format(now);
  const dateLabel = DATE_FMT.format(now);
  const lat = location.coords.latitude;
  const lon = location.coords.longitude;
  const coordsLabel = `${lat >= 0 ? 'N' : 'S'} ${Math.abs(lat).toFixed(2)} · ${lon >= 0 ? 'E' : 'W'} ${Math.abs(lon).toFixed(2)}`;

  return (
    <div className="hud-topbar" role="banner">
      {/* Hypermodern chrome */}
      <HudCornerBrackets />
      <HudLightTrace />

      {/* Left cluster */}
      <div className="hud-topbar__left">
        {/* LINK · SECURE status tag */}
        <span className="hud-topbar__tag" aria-label="Link secure">
          <span className="hud-topbar__tag-dot" aria-hidden="true" />
          {' '}LINK · SECURE
        </span>

        {/* Clock */}
        <span
          className="hud-topbar__clock"
          aria-label="Current time"
          aria-live="off"
        >
          {timeLabel}
        </span>

        {/* Date */}
        <span className="hud-topbar__date" aria-label="Current date">
          {dateLabel}
        </span>

        {/* Weather */}
        <WeatherWidget latitude={lat} longitude={lon} />

        {/* Coordinates */}
        <span className="hud-topbar__coords" aria-label="Location coordinates">
          {coordsLabel}
        </span>
      </div>

      {/* Center brand — absolutely centered */}
      <span className="hud-topbar__brand" aria-label="JARVIS Mark 42">
        J A R V I S / MK XLII
      </span>

      {/* Right cluster */}
      <div className="hud-topbar__right">
        <HudIconButton
          aria-label={idle ? 'Exit idle mode (Ctrl+.)' : 'Enter idle mode (Ctrl+.)'}
          onClick={onToggleIdle}
          active={idle}
        >
          <IdleIcon />
        </HudIconButton>

        <HudIconButton
          aria-label="Reset layout"
          onClick={onResetLayout}
        >
          <ResetIcon />
        </HudIconButton>

        <HudIconButton
          aria-label="Toggle tweaks panel"
          onClick={onToggleTweaks ?? (() => { /* stub — TweaksPanel is out of scope for this batch */ })}
          active={tweaksOpen}
        >
          <TweaksIcon />
        </HudIconButton>

        <HudIconButton
          aria-label="Open settings"
          onClick={onOpenSettings}
        >
          <SettingsIcon />
        </HudIconButton>
      </div>
    </div>
  );
}

export default HudTopBar;
