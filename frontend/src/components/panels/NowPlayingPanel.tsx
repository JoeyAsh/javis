import { useMemo } from 'react';
import type { ReactElement } from 'react';
import { nowPlayingMock } from '../../mock/nowPlayingMock';
import { useMockTicker } from '../../mock/useMockTicker';
import type { NowPlayingTrack, PanelMode } from '../../types';

export interface NowPlayingPanelProps {
  track?: NowPlayingTrack;
  mode?: PanelMode;
}

function formatMs(ms: number): string {
  const totalSec = Math.floor(ms / 1000);
  const m = Math.floor(totalSec / 60);
  const s = totalSec % 60;
  return `${m}:${String(s).padStart(2, '0')}`;
}

function useLiveProgress(track: NowPlayingTrack): number {
  const tick = useMockTicker(1000);
  return useMemo<number>(() => {
    if (!track.playing) return track.progressMs;
    return (track.progressMs + tick * 1000) % track.durationMs;
  }, [tick, track]);
}

function NowPlayingCompact({ track }: { track: NowPlayingTrack }): ReactElement {
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

function NowPlayingExpanded({ track }: { track: NowPlayingTrack }): ReactElement {
  const progress = useLiveProgress(track);
  const pct = Math.min(100, (progress / track.durationMs) * 100);
  return (
    <>
      <div style={{ display: 'flex', gap: 12, marginBottom: 10 }}>
        <div
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

      <div className="bar" style={{ marginBottom: 4 }}>
        <div className="bar-fill" style={{ width: `${pct}%` }} />
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
        <span className="mono-small">{formatMs(progress)}</span>
        <span className="mono-small">{formatMs(track.durationMs)}</span>
      </div>

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
        <TransportButton ariaLabel="Shuffle" active={track.shuffle}>⇌</TransportButton>
        <TransportButton ariaLabel="Previous">⏮</TransportButton>
        <TransportButton ariaLabel={track.playing ? 'Pause' : 'Play'} primary>
          {track.playing ? '⏸' : '▶'}
        </TransportButton>
        <TransportButton ariaLabel="Next">⏭</TransportButton>
        <TransportButton ariaLabel="Repeat" active={track.repeat !== 'off'}>↻</TransportButton>
      </div>
    </>
  );
}

interface TransportButtonProps {
  children: React.ReactNode;
  ariaLabel: string;
  primary?: boolean;
  active?: boolean;
}

function TransportButton({
  children,
  ariaLabel,
  primary = false,
  active = false,
}: TransportButtonProps): ReactElement {
  const size = primary ? 34 : 26;
  return (
    <button
      type="button"
      aria-label={ariaLabel}
      style={{
        width: size,
        height: size,
        background: primary ? 'var(--accent)' : 'transparent',
        border: `1px solid ${active ? 'var(--accent-bright)' : 'var(--border)'}`,
        borderRadius: 2,
        color: primary ? 'var(--bg)' : active ? 'var(--accent-bright)' : 'var(--text-secondary)',
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

export function NowPlayingPanel({
  track = nowPlayingMock,
  mode = 'expanded',
}: NowPlayingPanelProps): ReactElement {
  return mode === 'compact' ? (
    <NowPlayingCompact track={track} />
  ) : (
    <NowPlayingExpanded track={track} />
  );
}

export default NowPlayingPanel;
