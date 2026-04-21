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
 *   Weather (Open-Meteo) · Coords · ── CENTER BRAND ── · Icon cluster (5 btns)
 *
 * Right cluster order: Idle · Reset · Mic-Mute · SFX-Mute · Settings
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
      <span className="hud-topbar__weather-icon" aria-hidden="true">{weather.icon}</span>
      {tempLabel}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Icon SVGs
// ---------------------------------------------------------------------------

function IdleIcon(): ReactElement {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="8" />
      <path d="M12 4v2M12 18v2M4 12h2M18 12h2" />
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

function MicOnIcon(): ReactElement {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
      <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
      <line x1="12" y1="19" x2="12" y2="23" />
      <line x1="8" y1="23" x2="16" y2="23" />
    </svg>
  );
}

function MicOffIcon(): ReactElement {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="1" y1="1" x2="23" y2="23" />
      <path d="M9 9v3a3 3 0 0 0 5.12 2.12M15 9.34V4a3 3 0 0 0-5.94-.6" />
      <path d="M17 16.95A7 7 0 0 1 5 12v-2m14 0v2a7 7 0 0 1-.11 1.23" />
      <line x1="12" y1="19" x2="12" y2="23" />
      <line x1="8" y1="23" x2="16" y2="23" />
    </svg>
  );
}

function SpeakerOnIcon(): ReactElement {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
      <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
      <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
    </svg>
  );
}

function SpeakerOffIcon(): ReactElement {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
      <line x1="23" y1="9" x2="17" y2="15" />
      <line x1="17" y1="9" x2="23" y2="15" />
    </svg>
  );
}

function SettingsIcon(): ReactElement {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="5" cy="6" r="1.5" />
      <path d="M8 6h13M3 12h9M15 12h6M3 18h5M11 18h10" />
      <circle cx="13" cy="12" r="1.5" />
      <circle cx="9" cy="18" r="1.5" />
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
  micMuted: boolean;
  onToggleMicMute: () => void;
  sfxMuted: boolean;
  onToggleSfxMute: () => void;
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function HudTopBar({
  idle,
  onToggleIdle,
  onResetLayout,
  onOpenSettings,
  micMuted,
  onToggleMicMute,
  sfxMuted,
  onToggleSfxMute,
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
        {/* LINK · SECURE status tag — prototype .infobar .tag */}
        <span className="hud-topbar__tag" aria-label="Link secure">
          <span className="hud-topbar__tag-dot" aria-hidden="true" />
          LINK · SECURE
        </span>

        <span className="hud-topbar__sep" aria-hidden="true">◆</span>

        {/* Clock — prototype .infobar .t */}
        <span
          className="hud-topbar__clock"
          aria-label="Current time"
          aria-live="off"
        >
          {timeLabel}
        </span>

        <span className="hud-topbar__sep" aria-hidden="true">·</span>

        {/* Date — prototype .infobar .d */}
        <span className="hud-topbar__date" aria-label="Current date">
          {dateLabel}
        </span>

        <span className="hud-topbar__sep" aria-hidden="true">·</span>

        {/* Weather — prototype .infobar .w */}
        <WeatherWidget latitude={lat} longitude={lon} />

        <span className="hud-topbar__sep" aria-hidden="true">·</span>

        {/* Coordinates — prototype .infobar .d */}
        <span className="hud-topbar__coords" aria-label="Location coordinates">
          {coordsLabel}
        </span>
      </div>

      {/* Center brand — flex child with flex:1 text-align:center. Prototype: <div class="brand"> */}
      <div className="hud-topbar__brand" aria-label="JARVIS Mark 42">
        <b className="hud-topbar__brand-j">J</b>{' '}A R V I S{' '}
        <span className="hud-topbar__brand-mk">/ MK XLII</span>
      </div>

      {/* Right cluster — order: Idle · Reset · Mic-Mute · SFX-Mute · Settings */}
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
          aria-label={micMuted ? 'Unmute microphone' : 'Mute microphone'}
          onClick={onToggleMicMute}
          active={micMuted}
        >
          {micMuted ? <MicOffIcon /> : <MicOnIcon />}
        </HudIconButton>

        <HudIconButton
          aria-label={sfxMuted ? 'Unmute sound effects' : 'Mute sound effects'}
          onClick={onToggleSfxMute}
          active={sfxMuted}
        >
          {sfxMuted ? <SpeakerOffIcon /> : <SpeakerOnIcon />}
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
