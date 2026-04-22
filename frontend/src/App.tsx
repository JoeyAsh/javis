import { Mic, MicOff, Volume2, VolumeOff } from 'lucide-react';
import React, { ReactElement, useCallback, useEffect, useRef, useState } from 'react';
import { PanelAvailabilityProvider } from './components/hud/PanelAvailability';
import { useWindowManager, WindowManagerProvider } from './components/hud/WindowManager';
import { useLocation } from './hooks';
import { useAudioAnalyser } from './hooks/useAudioAnalyser';
import { useConversationMode } from './hooks/useConversationMode';
import { useMicStream } from './hooks/useMicStream';
import { useSettings } from './hooks/useSettings';
import { useWebSocket } from './hooks/useWebSocket';
import {
    Button,
    HUDShell,
    Icon,
    Label,
    type ManagedWindow,
    Metric,
    Orb,
    type PanelContentRenderProps,
    type PanelMode,
    type SlotId,
    TopBar,
    WindowManager,
} from './lib';
import { SfxProvider } from './lib/audio/SfxContext';
import { useAudioEngine } from './lib/audio/useAudioEngine';
import { useTauriWindowSfx } from './lib/audio/useTauriWindowSfx';
import type { AppOrbState } from './types';

/**
 * Main JARVIS application component.
 * Fullscreen orb, floating window HUD, top bar, status overlay.
 */
export function App(): ReactElement {
    return (
        <WindowManagerProvider>
            <PanelAvailabilityProvider>
                <AppInner />
            </PanelAvailabilityProvider>
        </WindowManagerProvider>
    );
}

function ExpandedContent({ label }: { label: string }): ReactElement {
    return (
        <div
            style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                height: '100%',
                padding: 16,
                gap: 10,
            }}
        >
            <span
                style={{
                    fontSize: 8,
                    letterSpacing: 3,
                    textTransform: 'uppercase',
                    color: 'var(--accent)',
                }}
            >
                UNDOCKED
            </span>
            <Label>{label}</Label>
            <span style={{ fontSize: 10, color: 'var(--text-secondary)', textAlign: 'center' }}>
                Drag header to move · resize via edges and corners · click ⊞ in header to dock back
            </span>
        </div>
    );
}

function CompactContent({ label }: { label: string }): ReactElement {
    return (
        <div
            style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                height: '100%',
                padding: 8,
                gap: 6,
            }}
        >
            <span
                style={{
                    fontSize: 8,
                    letterSpacing: 3,
                    textTransform: 'uppercase',
                    color: 'var(--text-muted)',
                }}
            >
                DOCKED
            </span>
            <Label dim>{label}</Label>
        </div>
    );
}

function makeRenderer(label: string): (props: PanelContentRenderProps) => ReactElement {
    return function Renderer({ mode }: PanelContentRenderProps): ReactElement {
        if (mode === 'expanded') return <ExpandedContent label={label} />;
        return <CompactContent label={label} />;
    };
}

const MANAGED_WINDOWS: ManagedWindow[] = [
    {
        id: 'win-system',
        title: 'SYSTEM',
        ix: '◈',
        itemRenderer: makeRenderer('SYSTEM'),
    },
    {
        id: 'win-transcript',
        title: 'TRANSCRIPT',
        ix: '▸',
        itemRenderer: makeRenderer('TRANSCRIPT'),
    },
    {
        id: 'win-agenda',
        title: 'AGENDA',
        ix: '▦',
        itemRenderer: makeRenderer('AGENDA'),
    },
    {
        id: 'win-nowplaying',
        title: 'NOW PLAYING',
        ix: '♫',
        itemRenderer: makeRenderer('NOW PLAYING'),
    },
];

const INITIAL_ASSIGNMENTS: Record<string, SlotId> = {
    'win-system': 'L1',
    'win-transcript': 'R1',
    'win-agenda': 'R2',
    'win-nowplaying': 'B1',
};

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
        const id = window.setInterval(() => {
            void load();
        }, WEATHER_TICK_MS);

        return () => {
            cancelled = true;
            window.clearInterval(id);
            controllerRef.current?.abort();
            controllerRef.current = null;
        };
    }, [latitude, longitude]);

    return <Metric value={weather.temperature} unit="°C" small={true} />;
}

function AppInner(): ReactElement {
    const [muted, setMuted] = useState(false);
    const [idle, setIdle] = useState(false);
    const [orbOverride] = useState<AppOrbState | null>(null);
    const [settingsOpen, setSettingsOpen] = useState(false);
    const settingsHook = useSettings();
    const {
        orbState,
        audioQueue,
        consumeAudio,
        wsRef,
        registerStopAudio,
        notifyAudioPlaying,
        connected,
    } = useWebSocket();
    const { isSpeaking, enqueue, stopAll } = useAudioAnalyser();

    const [now, setNow] = useState<Date>(() => new Date());
    const location = useLocation();

    // Tick clock every second
    useEffect(() => {
        const id = window.setInterval(() => {
            setNow(new Date());
        }, TIME_TICK_MS);
        return () => {
            window.clearInterval(id);
        };
    }, []);

    const timeLabel = TIME_FMT.format(now);
    const dateLabel = DATE_FMT.format(now);
    const lat = location.coords.latitude;
    const lon = location.coords.longitude;
    const coordsLabel = `${lat >= 0 ? 'N' : 'S'} ${Math.abs(lat).toFixed(2)} · ${lon >= 0 ? 'E' : 'W'} ${Math.abs(lon).toFixed(2)}`;

    const [assignments, setAssignments] = useState<Record<string, SlotId>>(INITIAL_ASSIGNMENTS);
    const [focusedId, setFocusedId] = useState<string | null>(null);
    const [modes, setModes] = useState<Record<string, PanelMode>>({});

    // Register the audio-stop callback so barge_in messages can stop playback.
    useEffect(() => {
        registerStopAudio(stopAll);
    }, [registerStopAudio, stopAll]);

    // Keep the WS hook informed of actual audio playback state so it can hold
    // the orb in `speaking` until the last clip finishes, even after the backend
    // has sent `status=idle`.
    useEffect(() => {
        notifyAudioPlaying(isSpeaking);
    }, [isSpeaking, notifyAudioPlaying]);
    const { resetAll } = useWindowManager();
    const followUp = useConversationMode();

    // SFX engine — manages Web Audio lifecycle and loop state.
    const {
        isMuted: sfxMuted,
        toggleMute: toggleSfxMute,
        playOneShot: sfxPlayOneShot,
        play: sfxPlay,
        stop: sfxStop,
    } = useAudioEngine(
        orbOverride ?? (followUp.active && orbState === 'listening' ? 'follow_up' : orbState),
        connected,
        settingsHook.settings.heartbeatEnabled,
    );

    // Wire Tauri window maximize/minimize events to SFX.
    useTauriWindowSfx({ playOneShot: sfxPlayOneShot });

    // Dev-override wins over live pipeline state. When override is null, the
    // orb follows the real pipeline (WebSocket → setOrbState). When a
    // follow-up window is active and no explicit state is set, fold that
    // into the orb state so it picks the `follow_up` visual preset.
    const effectiveOrbState: AppOrbState =
        orbOverride ?? (followUp.active && orbState === 'listening' ? 'follow_up' : orbState);

    // Stream raw PCM audio from the browser mic to the backend via WebSocket.
    // Only pause when explicitly muted. Keep streaming during TTS so the
    // backend barge-in monitor can actually see the user interrupt; echo
    // is handled by browser AEC (echoCancellation: true) plus the
    // backend's post-TTS grace window.
    useMicStream({ wsRef, paused: muted });

    // Feed incoming audio to the audio analyser queue (with per-clip volume and channel).
    useEffect(() => {
        if (audioQueue.length > 0) {
            const item = audioQueue[0];
            enqueue(item.data, item.volume, item.channel);
            consumeAudio();
        }
    }, [audioQueue, enqueue, consumeAudio]);

    // Ctrl+. toggles idle mode
    useEffect(() => {
        const onKey = (e: KeyboardEvent): void => {
            if (e.ctrlKey && e.key === '.') {
                e.preventDefault();
                setIdle((v) => !v);
            }
        };
        window.addEventListener('keydown', onKey);
        return () => {
            window.removeEventListener('keydown', onKey);
        };
    }, []);

    const handleResetLayout = useCallback(() => {
        resetAll();
    }, [resetAll]);

    const handleOpenSettings = useCallback(() => {
        setSettingsOpen(true);
    }, []);

    // Apply --panel-opacity from settings so all .window elements pick it up
    // without touching individual panel styles.
    const panelOpacityCssVar = {
        '--panel-opacity': settingsHook.settings.panelOpacity,
    } as React.CSSProperties;

    return (
        <SfxProvider playOneShot={sfxPlayOneShot} play={sfxPlay} stop={sfxStop}>
            <HUDShell
                orb={<Orb state={'idle'} rings={true} particles={true} />}
                idle={true}
                topbar={
                    <TopBar
                        left={
                            <div>
                                <WeatherWidget latitude={lat} longitude={lon} />
                            </div>
                        }
                        center={
                            <span className="text-[9px] text-text-secondary font-mono uppercase tracking-[2px]">
                                JARVIS · HUD SHELL PREVIEW
                            </span>
                        }
                        right={
                            <>
                                <Button
                                    size="sm"
                                    onClick={() => setMuted((prevState) => !prevState)}
                                >
                                    <Icon icon={muted ? MicOff : Mic} />
                                </Button>
                                <Button size="sm" onClick={toggleSfxMute}>
                                    <Icon icon={sfxMuted ? VolumeOff : Volume2} />
                                </Button>
                            </>
                        }
                    />
                }
                reactor={true}
                scene={{
                    grid: true,
                    scanlines: true,
                    stars: true,
                }}
                dock={
                    <WindowManager
                        windows={MANAGED_WINDOWS}
                        assignments={assignments}
                        onAssignmentsChange={setAssignments}
                        focusedId={focusedId}
                        onFocusChange={setFocusedId}
                        modes={modes}
                        onModesChange={setModes}
                    />
                }
            />
            {/*<div*/}
            {/*    className={`app fixed inset-0 w-screen h-screen overflow-hidden${effectiveOrbState === 'working' ? ' is-working' : ''}${idle ? ' idle' : ''}`}*/}
            {/*    style={{ ...panelOpacityCssVar }}*/}
            {/*>*/}
            {/*    /!* Viewport corner brackets — fixed to browser window edges, z-index 4 *!/*/}
            {/*    <HudViewportCorners />*/}

            {/*    /!* Animated scene background — z-index 2 *!/*/}
            {/*    <Scene grid scan stars />*/}

            {/*    /!* Reactor halo — standalone 900×900 glow under the orb, z-index 0 *!/*/}
            {/*    <Reactor />*/}

            {/*    /!* Orb — migrated to src/lib/primitives/Orb *!/*/}
            {/*    <div className="text-text-muted">[orb removed — migrated to src/lib]</div>*/}

            {/*    /!* Floating window HUD — z-index 10 *!/*/}
            {/*    <HudWindows idle={idle} orbState={effectiveOrbState} />*/}

            {/*    /!* Top bar — z-index 30 *!/*/}
            {/*    <HudTopBar*/}
            {/*        idle={idle}*/}
            {/*        onToggleIdle={() => {*/}
            {/*            setIdle((v) => !v);*/}
            {/*        }}*/}
            {/*        onResetLayout={handleResetLayout}*/}
            {/*        onOpenSettings={handleOpenSettings}*/}
            {/*        micMuted={muted}*/}
            {/*        onToggleMicMute={() => {*/}
            {/*            setMuted((m) => !m);*/}
            {/*        }}*/}
            {/*        sfxMuted={sfxMuted}*/}
            {/*        onToggleSfxMute={toggleSfxMute}*/}
            {/*    />*/}

            {/*    /!* Settings overlay — z-index 50, above everything *!/*/}
            {/*    <SettingsOverlay*/}
            {/*        open={settingsOpen}*/}
            {/*        onClose={() => {*/}
            {/*            setSettingsOpen(false);*/}
            {/*        }}*/}
            {/*        settingsHook={settingsHook}*/}
            {/*    />*/}

            {/*    /!* Bottom-center dock — PTT button, audio meters, state label + brand *!/*/}
            {/*    <Dock*/}
            {/*        orbState={effectiveOrbState}*/}
            {/*        wsRef={wsRef}*/}
            {/*        pttEnabled={settingsHook.settings.pushToTalk}*/}
            {/*    />*/}

            {/*    /!* Bottom-right keyboard hint *!/*/}
            {/*    <HudHint />*/}
            {/*</div>*/}
        </SfxProvider>
    );
}

export default App;
