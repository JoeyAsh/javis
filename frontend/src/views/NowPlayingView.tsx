/**
 * NowPlayingView — Spotify playback panel content.
 *
 * Replaces legacy components/panels/NowPlaying/NowPlayingPanel.tsx.
 * Uses lib Button, Label, Mono, ProgressBar.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { ReactElement } from 'react';
import { Button, Label, Mono, ProgressBar } from '../lib';
import { usePanelAvailable } from '../contexts/PanelAvailability';
import { useMockTicker } from '../mock/useMockTicker';
import { sendSpotifyCmdStream, subscribeSpotifyStateStream } from '../hooks/useWebSocket';
import type {
    NowPlayingTrack,
    PanelMode,
    SpotifyCmdAction,
    SpotifyStatePayload,
} from '../types';
import './NowPlayingView.css';

const SPOTIFY_AUTH_URL = 'http://127.0.0.1:8766/oauth/spotify/start';
const AVAILABILITY_TIMEOUT_MS = 10_000;
const WAVE_BARS = 7;

export interface NowPlayingViewProps {
    mode?: PanelMode;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function formatMs(ms: number): string {
    const totalSec = Math.floor(ms / 1000);
    const m = Math.floor(totalSec / 60);
    const s = totalSec % 60;
    return `${m}:${String(s).padStart(2, '0')}`;
}

function payloadToTrack(payload: SpotifyStatePayload): NowPlayingTrack | null {
    const { track } = payload;
    if (!track) return null;
    return {
        title: track.name,
        artist: track.artist,
        album: track.album,
        monogram: track.artist.slice(0, 3).toUpperCase(),
        albumArtUrl: track.albumArtUrl,
        progressMs: track.progressMs,
        durationMs: track.durationMs,
        playing: track.isPlaying,
        shuffle: false,
        repeat: 'off',
        device: payload.device?.name ?? '',
    };
}

function useLiveProgress(track: NowPlayingTrack): number {
    const tick = useMockTicker(1000);
    return useMemo<number>(() => {
        if (!track.playing) return track.progressMs;
        return (track.progressMs + tick * 1000) % track.durationMs;
    }, [tick, track]);
}

// ── WaveStrip ────────────────────────────────────────────────────────────────

function WaveStrip({ playing }: { playing: boolean }): ReactElement {
    return (
        <div className={`np-wave${playing ? '' : ' np-wave--paused'}`} aria-hidden>
            {Array.from({ length: WAVE_BARS }, (_, i) => (
                <div
                    key={i}
                    className="np-wave__bar"
                    style={{
                        height: `${30 + ((i * 17) % 70)}%`,
                        animationDelay: `${(i * 0.12).toFixed(2)}s`,
                    }}
                />
            ))}
        </div>
    );
}

// ── TrackInfo ────────────────────────────────────────────────────────────────

function TrackInfo({ track }: { track: NowPlayingTrack }): ReactElement {
    const hasArt = Boolean(track.albumArtUrl);
    return (
        <div className="np-track">
            {hasArt ? (
                <img src={track.albumArtUrl} alt={track.album} className="np-art" />
            ) : (
                <div className="np-art-placeholder" aria-label="Album art placeholder">
                    <Mono size="lg">{track.monogram}</Mono>
                </div>
            )}
            <div className="np-meta">
                <Mono size="md" className="np-title">{track.title}</Mono>
                <Mono size="sm" secondary>{track.artist}</Mono>
                <Mono size="xs" muted>{track.album}</Mono>
                <WaveStrip playing={track.playing} />
            </div>
        </div>
    );
}

// ── Transport ────────────────────────────────────────────────────────────────

function TransportControls({
    track,
    onCmd,
}: {
    track: NowPlayingTrack;
    onCmd: (action: SpotifyCmdAction) => void;
}): ReactElement {
    return (
        <div className="np-controls" data-no-drag>
            <Button variant="ghost" size="sm" onClick={() => onCmd('prev')} aria-label="Previous">
                ⏮
            </Button>
            <Button
                variant="ghost"
                size="sm"
                onClick={() => onCmd(track.playing ? 'pause' : 'play')}
                aria-label={track.playing ? 'Pause' : 'Play'}
            >
                {track.playing ? '⏸' : '▶'}
            </Button>
            <Button variant="ghost" size="sm" onClick={() => onCmd('next')} aria-label="Next">
                ⏭
            </Button>
        </div>
    );
}

// ── Expanded ─────────────────────────────────────────────────────────────────

function NowPlayingExpanded({
    track,
    onCmd,
}: {
    track: NowPlayingTrack;
    onCmd: (action: SpotifyCmdAction) => void;
}): ReactElement {
    const progress = useLiveProgress(track);
    const pct = Math.min(1, progress / track.durationMs);

    return (
        <div className="np-expanded">
            <TrackInfo track={track} />
            <div className="np-progress">
                <ProgressBar value={pct} height="normal" aria-label="Track progress" />
                <div className="np-times">
                    <Mono size="xs" muted>{formatMs(progress)}</Mono>
                    <Mono size="xs" muted>{formatMs(track.durationMs)}</Mono>
                </div>
            </div>
            <TransportControls track={track} onCmd={onCmd} />
        </div>
    );
}

// ── Compact ──────────────────────────────────────────────────────────────────

function NowPlayingCompact({
    track,
    onCmd,
}: {
    track: NowPlayingTrack;
    onCmd: (action: SpotifyCmdAction) => void;
}): ReactElement {
    const progress = useLiveProgress(track);
    const pct = Math.min(1, progress / track.durationMs);

    return (
        <div className="np-compact">
            <Mono size="sm">{track.title}</Mono>
            <Mono size="xs" secondary>{track.artist}</Mono>
            <div className="np-compact__row">
                <ProgressBar value={pct} className="flex-1" aria-label="Track progress" />
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => onCmd(track.playing ? 'pause' : 'play')}
                    aria-label={track.playing ? 'Pause' : 'Play'}
                >
                    {track.playing ? '⏸' : '▶'}
                </Button>
            </div>
        </div>
    );
}

// ── States ───────────────────────────────────────────────────────────────────

function UnauthenticatedState(): ReactElement {
    const handleConnect = useCallback(() => {
        window.open(SPOTIFY_AUTH_URL, '_blank', 'noopener,noreferrer');
    }, []);
    return (
        <div className="np-state">
            <Label>SPOTIFY — NICHT VERBUNDEN</Label>
            <Button variant="ghost" size="sm" onClick={handleConnect}>VERBINDEN</Button>
        </div>
    );
}

function NoPlaybackState(): ReactElement {
    return (
        <div className="np-state">
            <Label>NO ACTIVE PLAYBACK</Label>
        </div>
    );
}

// ── Entry point ──────────────────────────────────────────────────────────────

export function NowPlayingView({ mode = 'expanded' }: NowPlayingViewProps): ReactElement {
    const [spotifyPayload, setSpotifyPayload] = useState<SpotifyStatePayload | null>(null);
    const [backendAvailable, setBackendAvailable] = useState(true);
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
        });
        return () => {
            if (availabilityTimerRef.current) clearTimeout(availabilityTimerRef.current);
            unsub();
        };
    }, []);

    const sendCmd = useCallback((action: SpotifyCmdAction): void => {
        sendSpotifyCmdStream(action);
    }, []);

    if (!backendAvailable && spotifyPayload === null) {
        return (
            <div className="np-state">
                <Label>SPOTIFY — NICHT VERBUNDEN</Label>
                <Mono size="xs" muted>Warte auf Backend-Verbindung…</Mono>
            </div>
        );
    }

    if (spotifyPayload !== null) {
        if (!spotifyPayload.authenticated) return <UnauthenticatedState />;
        const liveTrack = payloadToTrack(spotifyPayload);
        if (!liveTrack) return <NoPlaybackState />;
        return mode === 'compact' ? (
            <NowPlayingCompact track={liveTrack} onCmd={sendCmd} />
        ) : (
            <NowPlayingExpanded track={liveTrack} onCmd={sendCmd} />
        );
    }

    return <NoPlaybackState />;
}

export default NowPlayingView;

