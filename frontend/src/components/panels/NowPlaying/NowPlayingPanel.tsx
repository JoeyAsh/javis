/**
 * NowPlayingPanel — panel body for Spotify playback control.
 * Returns only body content; the Window wrapper supplies chrome via HudPanel.
 *
 * Prototype reference: NowPlayingPanel() in JARVIS HUD Hypermodern.html
 * Art monogram + track meta + progress bar + transport controls + volume.
 *
 * SFX: click baked into buttons via HudButton (handled externally);
 * no additional SFX wired here beyond what the transport buttons dispatch.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { ReactElement } from 'react';
import { usePanelAvailable } from '../../../contexts/PanelAvailability';
import { useMockTicker } from '../../../mock/useMockTicker';
import { sendSpotifyCmdStream, subscribeSpotifyStateStream } from '../../../hooks/useWebSocket';
import type {
    NowPlayingTrack,
    PanelMode,
    SpotifyCmdAction,
    SpotifyStatePayload,
} from '../../../types';
import './NowPlayingPanel.css';

// ============ Constants ============

const SPOTIFY_AUTH_URL = 'http://127.0.0.1:8766/oauth/spotify/start';
const AVAILABILITY_TIMEOUT_MS = 10_000;
const WAVE_BARS = 7;

// ============ Helpers ============

function formatMs(ms: number): string {
    const totalSec = Math.floor(ms / 1000);
    const m = Math.floor(totalSec / 60);
    const s = totalSec % 60;
    return `${m}:${String(s).padStart(2, '0')}`;
}

function payloadToTrack(payload: SpotifyStatePayload): NowPlayingTrack | null {
    const { track } = payload;
    if (!track) return null;
    const monogram = track.artist.slice(0, 3).toUpperCase();
    return {
        title: track.name,
        artist: track.artist,
        album: track.album,
        monogram,
        albumArtUrl: track.albumArtUrl,
        progressMs: track.progressMs,
        durationMs: track.durationMs,
        playing: track.isPlaying,
        shuffle: false,
        repeat: 'off',
        device: payload.device?.name ?? '',
    };
}

// ============ Live progress ticker ============

function useLiveProgress(track: NowPlayingTrack): number {
    const tick = useMockTicker(1000);
    return useMemo<number>(() => {
        if (!track.playing) return track.progressMs;
        return (track.progressMs + tick * 1000) % track.durationMs;
    }, [tick, track]);
}

// ============ WaveStrip ============

function WaveStrip({ playing }: { playing: boolean }): ReactElement {
    return (
        <div className={`nowplaying-wave${playing ? '' : ' nowplaying-wave--paused'}`} aria-hidden>
            {Array.from({ length: WAVE_BARS }, (_, i) => (
                <div
                    key={i}
                    className="nowplaying-wave__bar"
                    style={{
                        height: `${30 + ((i * 17) % 70)}%`,
                        animationDelay: `${(i * 0.12).toFixed(2)}s`,
                    }}
                />
            ))}
        </div>
    );
}

// ============ TrackInfo ============

interface TrackInfoProps {
    track: NowPlayingTrack;
}

function TrackInfo({ track }: TrackInfoProps): ReactElement {
    const hasArt = Boolean(track.albumArtUrl);
    return (
        <div className="nowplaying-track">
            {hasArt ? (
                <img src={track.albumArtUrl} alt={track.album} className="nowplaying-art" />
            ) : (
                <div aria-label="Album art placeholder" className="nowplaying-art-placeholder">
                    {track.monogram}
                </div>
            )}
            <div className="nowplaying-meta">
                <div className="nowplaying-title">{track.title}</div>
                <div className="nowplaying-artist">{track.artist}</div>
                <div className="nowplaying-album">{track.album}</div>
                <WaveStrip playing={track.playing} />
            </div>
        </div>
    );
}

// ============ TransportControls ============

interface TransportControlsProps {
    track: NowPlayingTrack;
    onCmd: (action: SpotifyCmdAction, value?: number) => void;
}

function TransportControls({ track, onCmd }: TransportControlsProps): ReactElement {
    return (
        <div className="nowplaying-controls" data-no-drag>
            <button
                type="button"
                aria-label="Previous"
                className="nowplaying-tbtn"
                onClick={() => onCmd('prev')}
            >
                <svg viewBox="0 0 24 24" fill="currentColor">
                    <polygon points="18,5 8,12 18,19" />
                    <rect x="6" y="5" width="2" height="14" />
                </svg>
            </button>
            <button
                type="button"
                aria-label={track.playing ? 'Pause' : 'Play'}
                className="nowplaying-tbtn nowplaying-tbtn--primary"
                onClick={() => onCmd(track.playing ? 'pause' : 'play')}
            >
                {track.playing ? (
                    <svg viewBox="0 0 24 24" fill="currentColor">
                        <rect x="6" y="4" width="4" height="16" />
                        <rect x="14" y="4" width="4" height="16" />
                    </svg>
                ) : (
                    <svg viewBox="0 0 24 24" fill="currentColor">
                        <polygon points="6,3 21,12 6,21" />
                    </svg>
                )}
            </button>
            <button
                type="button"
                aria-label="Next"
                className="nowplaying-tbtn"
                onClick={() => onCmd('next')}
            >
                <svg viewBox="0 0 24 24" fill="currentColor">
                    <polygon points="6,5 16,12 6,19" />
                    <rect x="16" y="5" width="2" height="14" />
                </svg>
            </button>
        </div>
    );
}

// ============ Expanded view ============

interface NowPlayingExpandedProps {
    track: NowPlayingTrack;
    volumePercent: number;
    onCmd: (action: SpotifyCmdAction, value?: number) => void;
}

function NowPlayingExpanded({ track, onCmd }: NowPlayingExpandedProps): ReactElement {
    const progress = useLiveProgress(track);
    const pct = Math.min(100, (progress / track.durationMs) * 100);

    return (
        <div className="nowplaying-panel">
            <TrackInfo track={track} />
            <div className="nowplaying-progress">
                <div className="bar">
                    <div className="bar-fill" style={{ width: `${pct}%` }} />
                </div>
                <div className="nowplaying-times">
                    <span>{formatMs(progress)}</span>
                    <span>{formatMs(track.durationMs)}</span>
                </div>
            </div>
            <TransportControls track={track} onCmd={onCmd} />
        </div>
    );
}

// ============ Compact view ============

interface NowPlayingCompactProps {
    track: NowPlayingTrack;
    onCmd: (action: SpotifyCmdAction, value?: number) => void;
}

function NowPlayingCompact({ track, onCmd }: NowPlayingCompactProps): ReactElement {
    const progress = useLiveProgress(track);
    const pct = Math.min(100, (progress / track.durationMs) * 100);

    return (
        <div className="nowplaying-compact">
            <div className="nowplaying-compact__title">{track.title}</div>
            <div className="nowplaying-compact__artist">{track.artist}</div>
            <div className="nowplaying-compact__row">
                <div className="bar" style={{ flex: 1 }}>
                    <div className="bar-fill" style={{ width: `${pct}%` }} />
                </div>
                <button
                    type="button"
                    aria-label={track.playing ? 'Pause' : 'Play'}
                    data-no-drag
                    className="nowplaying-compact__playbtn"
                    onClick={() => onCmd(track.playing ? 'pause' : 'play')}
                >
                    {track.playing ? '⏸' : '▶'}
                </button>
            </div>
        </div>
    );
}

// ============ Auth / no-playback states ============

function UnauthenticatedState(): ReactElement {
    const handleConnect = useCallback(() => {
        window.open(SPOTIFY_AUTH_URL, '_blank', 'noopener,noreferrer');
    }, []);

    return (
        <div className="nowplaying-state">
            <span className="nowplaying-state__label">SPOTIFY — NICHT VERBUNDEN</span>
            <button
                type="button"
                aria-label="Log in to Spotify"
                className="nowplaying-state__btn"
                onClick={handleConnect}
            >
                VERBINDEN
            </button>
        </div>
    );
}

function NoPlaybackState(): ReactElement {
    return (
        <div className="nowplaying-state">
            <span className="nowplaying-state__label">NO ACTIVE PLAYBACK</span>
        </div>
    );
}

// ============ Panel props & main component ============

export interface NowPlayingPanelProps {
    mode?: PanelMode;
}

/**
 * NowPlayingPanel — subscribes to `spotify_state` WS frames via the
 * module-level stream helper. Shows NoPlaybackState until first live frame
 * arrives. Returns null if no frame arrives within AVAILABILITY_TIMEOUT_MS.
 */
export function NowPlayingPanel({ mode = 'expanded' }: NowPlayingPanelProps): ReactElement | null {
    const [spotifyPayload, setSpotifyPayload] = useState<SpotifyStatePayload | null>(null);
    const [backendAvailable, setBackendAvailable] = useState(true);
    const [volumePercent, setVolumePercent] = useState(50);
    const availabilityTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    usePanelAvailable('nowplaying', backendAvailable || spotifyPayload !== null);

    useEffect(() => {
        availabilityTimerRef.current = setTimeout(() => {
            setBackendAvailable(false);
        }, AVAILABILITY_TIMEOUT_MS);

        const unsub = subscribeSpotifyStateStream((payload) => {
            if (availabilityTimerRef.current) clearTimeout(availabilityTimerRef.current);
            setBackendAvailable(true);
            setSpotifyPayload(payload);
            if (payload.device?.volumePercent !== undefined) {
                setVolumePercent(payload.device.volumePercent);
            }
        });
        return () => {
            if (availabilityTimerRef.current) clearTimeout(availabilityTimerRef.current);
            unsub();
        };
    }, []);

    // Stable command sender.
    const sendCmd = useCallback((action: SpotifyCmdAction, value?: number): void => {
        sendSpotifyCmdStream(action, value);
    }, []);

    // Backend not available — hide the panel.
    if (!backendAvailable && spotifyPayload === null) return null;

    // Render live data when available.
    if (spotifyPayload !== null) {
        if (!spotifyPayload.authenticated) {
            return <UnauthenticatedState />;
        }
        const liveTrack = payloadToTrack(spotifyPayload);
        if (!liveTrack) {
            return <NoPlaybackState />;
        }
        return mode === 'compact' ? (
            <NowPlayingCompact track={liveTrack} onCmd={sendCmd} />
        ) : (
            <NowPlayingExpanded track={liveTrack} volumePercent={volumePercent} onCmd={sendCmd} />
        );
    }

    // Waiting for first frame — show empty state.
    return <NoPlaybackState />;
}

export default NowPlayingPanel;
