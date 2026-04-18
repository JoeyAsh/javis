import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { ReactElement } from 'react';
import { nowPlayingMock } from '../../mock/nowPlayingMock';
import { useMockTicker } from '../../mock/useMockTicker';
import {
  sendSpotifyCmdStream,
  subscribeSpotifyStateStream,
} from '../../hooks/useWebSocket';
import type {
  NowPlayingTrack,
  PanelMode,
  SpotifyCmdAction,
  SpotifyStatePayload,
} from '../../types';

// ============ Auth URL ============

const SPOTIFY_AUTH_URL = 'http://127.0.0.1:8766/oauth/spotify/start';
const MOCK_GRACE_MS = 2000;

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

// ============ Transport button ============

interface TransportButtonProps {
  children: React.ReactNode;
  ariaLabel: string;
  primary?: boolean;
  active?: boolean;
  onClick?: () => void;
}

function TransportButton({
  children,
  ariaLabel,
  primary = false,
  active = false,
  onClick,
}: TransportButtonProps): ReactElement {
  const size = primary ? 34 : 26;
  return (
    <button
      type="button"
      aria-label={ariaLabel}
      onClick={onClick}
      style={{
        width: size,
        height: size,
        background: primary ? 'var(--accent)' : 'transparent',
        border: `1px solid ${active ? 'var(--accent-bright)' : 'var(--border)'}`,
        borderRadius: 2,
        color: primary
          ? 'var(--bg)'
          : active
            ? 'var(--accent-bright)'
            : 'var(--text-secondary)',
        cursor: 'pointer',
        fontFamily: 'var(--font)',
        fontSize: primary ? 14 : 12,
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        lineHeight: 1,
      }}
    >
      {children}
    </button>
  );
}

// ============ TrackInfo sub-component ============

interface TrackInfoProps {
  track: NowPlayingTrack;
}

function TrackInfo({ track }: TrackInfoProps): ReactElement {
  const hasArt = Boolean(track.albumArtUrl);
  return (
    <div style={{ display: 'flex', gap: 12, marginBottom: 10 }}>
      {hasArt ? (
        <img
          src={track.albumArtUrl}
          alt={track.album}
          width={56}
          height={56}
          style={{
            width: 56,
            height: 56,
            objectFit: 'cover',
            flexShrink: 0,
            borderRadius: 2,
            boxShadow: 'var(--glow)',
          }}
        />
      ) : (
        <div
          aria-label="Album art placeholder"
          style={{
            width: 56,
            height: 56,
            background: 'var(--accent)',
            color: 'var(--bg)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 14,
            fontWeight: 700,
            letterSpacing: 1,
            flexShrink: 0,
            borderRadius: 2,
            boxShadow: 'var(--glow)',
          }}
        >
          {track.monogram}
        </div>
      )}
      <div style={{ minWidth: 0, flex: 1 }}>
        <div
          style={{
            fontSize: 13,
            color: 'var(--text)',
            marginBottom: 2,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {track.title}
        </div>
        <div
          style={{
            fontSize: 11,
            color: 'var(--text-secondary)',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {track.artist}
        </div>
        <div
          style={{
            fontSize: 10,
            color: 'var(--text-muted)',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {track.album}
        </div>
      </div>
    </div>
  );
}

// ============ TransportControls sub-component ============

interface TransportControlsProps {
  track: NowPlayingTrack;
  onCmd: (action: SpotifyCmdAction, value?: number) => void;
}

function TransportControls({ track, onCmd }: TransportControlsProps): ReactElement {
  return (
    <div
      data-no-drag
      style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        gap: 8,
        marginTop: 10,
      }}
    >
      <TransportButton ariaLabel="Previous" onClick={() => onCmd('prev')}>
        ⏮
      </TransportButton>
      <TransportButton
        ariaLabel={track.playing ? 'Pause' : 'Play'}
        primary
        onClick={() => onCmd(track.playing ? 'pause' : 'play')}
      >
        {track.playing ? '⏸' : '▶'}
      </TransportButton>
      <TransportButton ariaLabel="Next" onClick={() => onCmd('next')}>
        ⏭
      </TransportButton>
    </div>
  );
}

// ============ VolumeSlider sub-component ============

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
    <div
      style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 8 }}
      data-no-drag
    >
      <span style={{ fontSize: 9, color: 'var(--text-muted)', letterSpacing: 1 }}>VOL</span>
      <input
        type="range"
        min={0}
        max={100}
        defaultValue={volume}
        onChange={handleChange}
        aria-label="Volume"
        style={{ flex: 1, accentColor: 'var(--accent)', cursor: 'pointer' }}
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

function NowPlayingExpanded({
  track,
  volumePercent,
  onCmd,
}: NowPlayingExpandedProps): ReactElement {
  const progress = useLiveProgress(track);
  const pct = Math.min(100, (progress / track.durationMs) * 100);
  return (
    <>
      <TrackInfo track={track} />
      <div className="bar" style={{ marginBottom: 4 }}>
        <div className="bar-fill" style={{ width: `${pct}%` }} />
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
        <span className="mono-small">{formatMs(progress)}</span>
        <span className="mono-small">{formatMs(track.durationMs)}</span>
      </div>
      <TransportControls track={track} onCmd={onCmd} />
      <VolumeSlider volume={volumePercent} onCmd={onCmd} />
    </>
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
    <>
      <div className="window-compact-row truncate" style={{ fontSize: 12, color: 'var(--text)' }}>
        {track.title}
      </div>
      <div
        className="window-compact-row truncate"
        style={{ fontSize: 10, color: 'var(--text-muted)' }}
      >
        {track.artist}
      </div>
      <div className="window-compact-row" style={{ gap: 8, marginTop: 6 }}>
        <div className="bar" style={{ flex: 1 }}>
          <div className="bar-fill" style={{ width: `${pct}%` }} />
        </div>
        <button
          type="button"
          aria-label={track.playing ? 'Pause' : 'Play'}
          data-no-drag
          onClick={() => onCmd(track.playing ? 'pause' : 'play')}
          style={{
            width: 20,
            height: 20,
            background: 'transparent',
            border: '1px solid var(--border)',
            borderRadius: 2,
            color: 'var(--accent-bright)',
            cursor: 'pointer',
            fontFamily: 'var(--font)',
            fontSize: 10,
            lineHeight: 1,
            flexShrink: 0,
          }}
        >
          {track.playing ? '\u23F8' : '\u25B6'}
        </button>
      </div>
    </>
  );
}

// ============ Unauthenticated state ============

function UnauthenticatedState(): ReactElement {
  const handleConnect = useCallback(() => {
    window.open(SPOTIFY_AUTH_URL, '_blank', 'noopener,noreferrer');
  }, []);

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 10,
        padding: '16px 0',
      }}
    >
      <span style={{ fontSize: 10, color: 'var(--text-muted)', letterSpacing: 1 }}>
        SPOTIFY — NICHT VERBUNDEN
      </span>
      <button
        type="button"
        aria-label="Log in to Spotify"
        onClick={handleConnect}
        style={{
          padding: '6px 16px',
          background: 'transparent',
          border: '1px solid var(--accent)',
          borderRadius: 2,
          color: 'var(--accent)',
          cursor: 'pointer',
          fontFamily: 'var(--font)',
          fontSize: 11,
          letterSpacing: 1,
        }}
      >
        VERBINDEN
      </button>
    </div>
  );
}

// ============ No active playback state ============

function NoPlaybackState(): ReactElement {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '16px 0',
        fontSize: 10,
        color: 'var(--text-muted)',
        letterSpacing: 1,
      }}
    >
      NO ACTIVE PLAYBACK
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

  // Stable command sender — delegates to the module-level sender so no WS
  // ref prop-drilling is needed.
  const sendCmd = useCallback(
    (action: SpotifyCmdAction, value?: number) => {
      sendSpotifyCmdStream(action, value);
    },
    [],
  );

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
