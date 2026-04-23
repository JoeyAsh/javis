/**
 * JarvisTopBar — JARVIS-specific top bar content wired into lib TopBar slots.
 *
 * Left:   LINK·SECURE tag, clock, date, weather, coordinates
 * Center: JARVIS / MK XLII brand
 * Right:  Idle, Reset, Mic-Mute, SFX-Mute, Settings icon buttons
 */

import { useEffect, useRef, useState } from 'react';
import type { ReactElement } from 'react';
import { Crosshair, Mic, MicOff, RotateCcw, Settings, Volume2, VolumeX } from 'lucide-react';
import { Button, Icon, TopBar } from '../lib';
import { useLocation } from '@common/hooks/useLocation';
import './JarvisTopBar.css';

// ── Constants ────────────────────────────────────────────────────────────────

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

// ── Weather ──────────────────────────────────────────────────────────────────

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
                    temperature:
                        cur.temperature_2m !== undefined ? Math.round(cur.temperature_2m) : null,
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
        const id = window.setInterval(() => void load(), WEATHER_TICK_MS);
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
            className={`jtb__weather${weather.stale ? ' jtb__weather--stale' : ''}`}
            aria-label="Current weather"
        >
            <span className="jtb__weather-icon" aria-hidden="true">
                {weather.icon}
            </span>
            {tempLabel}
        </span>
    );
}

// ── Props ────────────────────────────────────────────────────────────────────

export interface JarvisTopBarProps {
    idle: boolean;
    onToggleIdle: () => void;
    onResetLayout: () => void;
    onOpenSettings: () => void;
    micMuted: boolean;
    onToggleMicMute: () => void;
    sfxMuted: boolean;
    onToggleSfxMute: () => void;
}

// ── Component ────────────────────────────────────────────────────────────────

export function JarvisTopBar({
    idle,
    onToggleIdle,
    onResetLayout,
    onOpenSettings,
    micMuted,
    onToggleMicMute,
    sfxMuted,
    onToggleSfxMute,
}: JarvisTopBarProps): ReactElement {
    const [now, setNow] = useState<Date>(() => new Date());
    const location = useLocation();

    useEffect(() => {
        const id = window.setInterval(() => setNow(new Date()), TIME_TICK_MS);
        return () => window.clearInterval(id);
    }, []);

    const timeLabel = TIME_FMT.format(now);
    const dateLabel = DATE_FMT.format(now);
    const lat = location.coords.latitude;
    const lon = location.coords.longitude;
    const coordsLabel = `${lat >= 0 ? 'N' : 'S'} ${Math.abs(lat).toFixed(2)} · ${lon >= 0 ? 'E' : 'W'} ${Math.abs(lon).toFixed(2)}`;

    return (
        <TopBar
            left={
                <div className="jtb__left">
                    <span className="jtb__tag" aria-label="Link secure">
                        <span className="jtb__tag-dot" aria-hidden="true" />
                        LINK · SECURE
                    </span>
                    <span className="jtb__sep" aria-hidden="true">◆</span>
                    <span className="jtb__clock" aria-label="Current time">{timeLabel}</span>
                    <span className="jtb__sep" aria-hidden="true">·</span>
                    <span className="jtb__date" aria-label="Current date">{dateLabel}</span>
                    <span className="jtb__sep" aria-hidden="true">·</span>
                    <WeatherWidget latitude={lat} longitude={lon} />
                    <span className="jtb__sep" aria-hidden="true">·</span>
                    <span className="jtb__coords" aria-label="Location coordinates">
                        {coordsLabel}
                    </span>
                </div>
            }
            center={
                <div className="jtb__brand" aria-label="JARVIS Mark 42">
                    <b className="jtb__brand-j">J</b> A R V I S{' '}
                    <span className="jtb__brand-mk">/ MK XLII</span>
                </div>
            }
            right={
                <div className="jtb__right">
                    <Button
                        variant="ghost"
                        size="sm"
                        aria-label={idle ? 'Exit idle mode (Ctrl+.)' : 'Enter idle mode (Ctrl+.)'}
                        onClick={onToggleIdle}
                        className={`jtb__icon-btn${idle ? ' jtb__icon-btn--active' : ''}`}
                    >
                        <Icon icon={Crosshair} size="sm" aria-hidden="true" />
                    </Button>
                    <Button
                        variant="ghost"
                        size="sm"
                        aria-label="Reset layout"
                        onClick={onResetLayout}
                        className="jtb__icon-btn"
                    >
                        <Icon icon={RotateCcw} size="sm" aria-hidden="true" />
                    </Button>
                    <Button
                        variant="ghost"
                        size="sm"
                        aria-label={micMuted ? 'Unmute microphone' : 'Mute microphone'}
                        onClick={onToggleMicMute}
                        className={`jtb__icon-btn${micMuted ? ' jtb__icon-btn--active' : ''}`}
                    >
                        <Icon icon={micMuted ? MicOff : Mic} size="sm" aria-hidden="true" />
                    </Button>
                    <Button
                        variant="ghost"
                        size="sm"
                        aria-label={sfxMuted ? 'Unmute sound effects' : 'Mute sound effects'}
                        onClick={onToggleSfxMute}
                        className={`jtb__icon-btn${sfxMuted ? ' jtb__icon-btn--active' : ''}`}
                    >
                        <Icon icon={sfxMuted ? VolumeX : Volume2} size="sm" aria-hidden="true" />
                    </Button>
                    <Button
                        variant="ghost"
                        size="sm"
                        aria-label="Open settings"
                        onClick={onOpenSettings}
                        className="jtb__icon-btn"
                    >
                        <Icon icon={Settings} size="sm" aria-hidden="true" />
                    </Button>
                </div>
            }
        />
    );
}

export default JarvisTopBar;

