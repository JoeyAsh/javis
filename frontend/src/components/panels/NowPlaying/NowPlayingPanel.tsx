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
import { nowPlayingMock } from '../../../mock/nowPlayingMock';
import { useMockTicker } from '../../../mock/useMockTicker';
import {
  sendSpotifyCmdStream,
  subscribeSpotifyStateStream,
} from '../../../hooks/useWebSocket';
import type {
  NowPlayingTrack,
  PanelMode,
  SpotifyCmdAction,
  SpotifyStatePayload,
} from '../../../types';
import './NowPlayingPanel.css';

// ============ Constants ============

const SPOTIFY_AUTH_URL = 'http://127.0.0.1:8766/oauth/spotify/start';
const MOCK_GRACE_MS = 2000;
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
        <img
          src={track.albumArtUrl}
          alt={track.album}
          className="nowplaying-art"
        />
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

// ============ VolumeSlider ============

interface VolumeSliderProps {
  volume: number;
  onCmd: (action: SpotifyCmdAction, value?: number) => void;
}

function VolumeSlider({ volume, onCmd }: VolumeSliderProps): ReactElement {
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const pct = Number(e.target.value);
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => {
        onCmd('volume', pct);
      }, 200);
    },
    [onCmd],
  );

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  return (
    <div className="nowplaying-volume" data-no-drag>
      <span className="nowplaying-vol-label">VOL</span>
      <input
        type="range"
        min={0}
        max={100}
        defaultValue={volume}
        onChange={handleChange}
        aria-label="Volume"
      />
    </div>
  );
}

// ============ Expanded view ============

interface NowPlayingExpandedProps {
  track: NowPlayingTrack;
  volumePercent: number;
  onCmd: (action: SpotifyCmdAction, value?: number) => void;
}

function NowPlayingExpanded({ track, volumePercent, onCmd }: NowPlayingExpandedProps): ReactElement {
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
      <VolumeSlider volume={volumePercent} onCmd={onCmd} />
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
 * module-level stream helper. Falls back to mock data for the first 2 s
 * after mount if no live frame has arrived yet.
 */
export function NowPlayingPanel({ mode = 'expanded' }: NowPlayingPanelProps): ReactElement {
  const [spotifyPayload, setSpotifyPayload] = useState<SpotifyStatePayload | null>(null);
  const [useMock, setUseMock] = useState(false);
  const [volumePercent, setVolumePercent] = useState(50);

  // Grace-period: show mock after 2 s if no live frame has arrived.
  useEffect(() => {
    const timer = setTimeout(() => {
      setUseMock(true);
    }, MOCK_GRACE_MS);
    return () => clearTimeout(timer);
  }, []);

  // Subscribe to live spotify_state frames.
  useEffect(() => {
    const unsub = subscribeSpotifyStateStream((payload) => {
      setSpotifyPayload(payload);
      if (payload.device?.volumePercent !== undefined) {
        setVolumePercent(payload.device.volumePercent);
      }
    });
    return unsub;
  }, []);

  // Stable command sender.
  const sendCmd = useCallback((action: SpotifyCmdAction, value?: number): void => {
    sendSpotifyCmdStream(action, value);
  }, []);

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

  // Before grace period: show empty state; after: show mock.
  if (!useMock) {
    return <NoPlaybackState />;
  }

  const noopCmd = (_action: SpotifyCmdAction, _value?: number): void => undefined;

  return mode === 'compact' ? (
    <NowPlayingCompact track={nowPlayingMock} onCmd={noopCmd} />
  ) : (
    <NowPlayingExpanded track={nowPlayingMock} volumePercent={volumePercent} onCmd={noopCmd} />
  );
}

export default NowPlayingPanel;
