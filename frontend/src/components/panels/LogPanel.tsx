/**
 * LogPanel — two-tab HUD panel:
 *   1. Raw Log Stream — live backend log lines with severity colouring.
 *   2. Turn Timeline — Gantt-style waterfall for the last 5 voice turns.
 *
 * Design: JetBrains Mono, CSS variables, sharp corners (<= 4px radius).
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { CSSProperties, ReactElement } from 'react';
import type { LogLevel, LogLinePayload, PanelMode, TurnTimingPayload } from '../../types';
import { useLogStream } from '../../hooks/useLogStream';
import { useTurnTimings } from '../../hooks/useTurnTimings';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface LogPanelProps {
  mode: PanelMode;
}

type TabId = 'stream' | 'timeline';

// ---------------------------------------------------------------------------
// Severity colour mapping (CSS variable names)
// ---------------------------------------------------------------------------

const LEVEL_COLOR: Record<LogLevel, string> = {
  DEBUG: 'var(--text-muted)',
  INFO: 'var(--text-secondary)',
  WARNING: '#c8a840',
  ERROR: '#d45757',
  CRITICAL: '#ff4444',
};

// ---------------------------------------------------------------------------
// Log-line row (memoized for perf)
// ---------------------------------------------------------------------------

interface LogRowProps {
  entry: LogLinePayload;
}

function LogRow({ entry }: LogRowProps): ReactElement {
  const ts = useMemo(() => {
    const d = new Date(entry.timestamp);
    return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}`;
  }, [entry.timestamp]);

  const color = LEVEL_COLOR[entry.level] ?? 'var(--text-secondary)';

  return (
    <div
      style={{
        display: 'flex',
        gap: 6,
        padding: '1px 6px',
        fontFamily: 'var(--font)',
        fontSize: 10,
        lineHeight: '1.5',
        borderBottom: '1px solid rgba(26,26,46,0.4)',
        contain: 'content',
      }}
    >
      <span style={{ color: 'var(--text-muted)', flexShrink: 0, userSelect: 'none' }}>
        {ts}
      </span>
      <span
        style={{
          color,
          flexShrink: 0,
          width: 52,
          fontWeight: entry.level === 'ERROR' || entry.level === 'CRITICAL' ? 700 : 400,
          userSelect: 'none',
        }}
      >
        {entry.level}
      </span>
      <span style={{ color: 'var(--text-muted)', flexShrink: 0, maxWidth: 80, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {entry.module}
      </span>
      <span style={{ color: 'var(--text)', wordBreak: 'break-word', flex: 1 }}>
        {entry.message}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Log Stream tab
// ---------------------------------------------------------------------------

const VISIBLE_LINES = 100;

interface StreamViewProps {
  paused: boolean;
}

function StreamView({ paused }: StreamViewProps): ReactElement {
  const { lines, clear } = useLogStream(500);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [hovering, setHovering] = useState(false);

  // Auto-scroll when not paused/hovering
  useEffect(() => {
    if (!hovering && !paused && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [lines, hovering, paused]);

  // Only render the last VISIBLE_LINES entries — avoid 500 DOM nodes.
  const visible = useMemo(() => {
    if (lines.length <= VISIBLE_LINES) return lines;
    return lines.slice(lines.length - VISIBLE_LINES);
  }, [lines]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Toolbar */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '3px 8px',
          borderBottom: '1px solid var(--border)',
          flexShrink: 0,
        }}
      >
        <span
          style={{
            fontFamily: 'var(--font)',
            fontSize: 9,
            color: 'var(--text-muted)',
            letterSpacing: '0.05em',
          }}
        >
          {lines.length} lines
          {hovering ? ' — paused' : ''}
        </span>
        <button
          type="button"
          onClick={clear}
          style={{
            fontFamily: 'var(--font)',
            fontSize: 9,
            color: 'var(--text-secondary)',
            background: 'none',
            border: '1px solid var(--border)',
            borderRadius: 2,
            padding: '1px 6px',
            cursor: 'pointer',
          }}
        >
          CLEAR
        </button>
      </div>

      {/* Scroll area */}
      <div
        ref={scrollRef}
        onMouseEnter={() => setHovering(true)}
        onMouseLeave={() => setHovering(false)}
        style={{
          flex: 1,
          overflowY: 'auto',
          overflowX: 'hidden',
          contain: 'strict',
        }}
      >
        {visible.length === 0 ? (
          <div
            style={{
              padding: '12px 8px',
              fontFamily: 'var(--font)',
              fontSize: 10,
              color: 'var(--text-muted)',
              textAlign: 'center',
            }}
          >
            Waiting for log stream…
          </div>
        ) : (
          visible.map((entry) => (
            <LogRow key={`${entry.timestamp}-${entry.message.slice(0, 16)}`} entry={entry} />
          ))
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Turn Timeline (Gantt waterfall)
// ---------------------------------------------------------------------------

interface TurnTimingBarProps {
  label: string;
  startMs: number | null;
  endMs: number | null;
  domainStartMs: number;
  domainDurationMs: number;
  color: string;
}

function TurnTimingBar({
  label,
  startMs,
  endMs,
  domainStartMs,
  domainDurationMs,
  color,
}: TurnTimingBarProps): ReactElement | null {
  if (startMs === null || endMs === null || domainDurationMs <= 0) return null;

  const left = ((startMs - domainStartMs) / domainDurationMs) * 100;
  const width = ((endMs - startMs) / domainDurationMs) * 100;
  const duration = Math.round(endMs - startMs);

  const barStyle: CSSProperties = {
    position: 'absolute',
    top: '50%',
    transform: 'translateY(-50%)',
    left: `${Math.max(0, left)}%`,
    width: `${Math.max(0.5, width)}%`,
    height: 10,
    background: color,
    borderRadius: 1,
    cursor: 'default',
    transition: 'opacity 150ms',
  };

  return (
    <div style={{ position: 'relative', height: 22, display: 'flex', alignItems: 'center' }}>
      <span
        style={{
          fontFamily: 'var(--font)',
          fontSize: 8,
          color: 'var(--text-muted)',
          width: 62,
          flexShrink: 0,
          textTransform: 'uppercase',
          letterSpacing: '0.04em',
          paddingRight: 4,
        }}
      >
        {label}
      </span>
      <div style={{ flex: 1, position: 'relative', height: '100%' }}>
        <div style={barStyle} title={`${label}: ${duration} ms`} />
      </div>
      <span
        style={{
          fontFamily: 'var(--font)',
          fontSize: 8,
          color: 'var(--text-secondary)',
          width: 38,
          textAlign: 'right',
          flexShrink: 0,
        }}
      >
        {duration}ms
      </span>
    </div>
  );
}

interface TurnCardProps {
  turn: TurnTimingPayload;
  index: number;
  domainStartMs: number;
  domainDurationMs: number;
}

const PHASE_COLORS: ReadonlyArray<string> = [
  '#4ca8e8',  // STT — accent
  '#6ec4ff',  // LLM wait — accent-bright
  '#3d8abf',  // Streaming
  '#5ab8f0',  // TTS first — accent-speak
  '#38849e',  // TTS total
];

function TurnCard({ turn, index, domainStartMs, domainDurationMs }: TurnCardProps): ReactElement {
  const phases = useMemo(() => [
    {
      label: 'STT',
      startMs: turn.audio_end_ts,
      endMs: turn.stt_done_ts,
      color: PHASE_COLORS[0],
    },
    {
      label: 'LLM wait',
      startMs: turn.stt_done_ts,
      endMs: turn.llm_first_token_ts,
      color: PHASE_COLORS[1],
    },
    {
      label: 'Streaming',
      startMs: turn.llm_first_token_ts,
      endMs: turn.llm_done_ts,
      color: PHASE_COLORS[2],
    },
    {
      label: 'TTS first',
      startMs: turn.llm_first_token_ts,
      endMs: turn.tts_first_audio_ts,
      color: PHASE_COLORS[3],
    },
    {
      label: 'TTS total',
      startMs: turn.tts_first_audio_ts,
      endMs: turn.tts_done_ts,
      color: PHASE_COLORS[4],
    },
  ], [turn]);

  const totalMs = Math.round(turn.tts_done_ts - turn.audio_end_ts);

  return (
    <div
      style={{
        padding: '4px 6px',
        borderBottom: '1px solid var(--border)',
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          marginBottom: 2,
        }}
      >
        <span
          style={{
            fontFamily: 'var(--font)',
            fontSize: 8,
            color: 'var(--text-muted)',
            letterSpacing: '0.08em',
          }}
        >
          TURN {index + 1} · {turn.turn_id}
        </span>
        <span
          style={{
            fontFamily: 'var(--font)',
            fontSize: 8,
            color: 'var(--accent)',
          }}
        >
          {totalMs}ms total
        </span>
      </div>

      {phases.map((phase) => (
        <TurnTimingBar
          key={phase.label}
          label={phase.label}
          startMs={phase.startMs}
          endMs={phase.endMs}
          domainStartMs={domainStartMs}
          domainDurationMs={domainDurationMs}
          color={phase.color}
        />
      ))}
    </div>
  );
}

interface TimelineViewProps {
  // no extra props; self-contained
}

function TimelineView(_props: TimelineViewProps): ReactElement {
  const { turns } = useTurnTimings();

  // Compute shared time domain across all turns for grid alignment.
  const { domainDurationMs } = useMemo(() => {
    if (turns.length === 0) {
      return { domainDurationMs: 1 };
    }
    // For cross-turn grid alignment we use the longest turn as the domain.
    const maxDuration = Math.max(
      ...turns.map((t) => t.tts_done_ts - t.audio_end_ts),
      1,
    );
    return { domainDurationMs: maxDuration };
  }, [turns]);

  if (turns.length === 0) {
    return (
      <div
        style={{
          padding: '16px 8px',
          fontFamily: 'var(--font)',
          fontSize: 10,
          color: 'var(--text-muted)',
          textAlign: 'center',
        }}
      >
        No voice turns yet — speak to JARVIS to populate the timeline.
      </div>
    );
  }

  return (
    <div style={{ overflowY: 'auto', height: '100%', contain: 'strict' }}>
      {turns.map((turn, i) => (
        <TurnCard
          key={turn.turn_id}
          turn={turn}
          index={i}
          domainStartMs={turn.audio_end_ts}
          domainDurationMs={domainDurationMs}
        />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// LogPanel root
// ---------------------------------------------------------------------------

export function LogPanel({ mode }: LogPanelProps): ReactElement {
  const [activeTab, setActiveTab] = useState<TabId>('stream');

  const handleTabClick = useCallback((tab: TabId) => {
    setActiveTab(tab);
  }, []);

  const tabStyle = useCallback(
    (tab: TabId): CSSProperties => ({
      fontFamily: 'var(--font)',
      fontSize: 9,
      letterSpacing: '0.08em',
      textTransform: 'uppercase',
      color: activeTab === tab ? 'var(--accent)' : 'var(--text-muted)',
      background: 'none',
      border: 'none',
      borderBottom: activeTab === tab ? '1px solid var(--accent)' : '1px solid transparent',
      padding: '3px 8px 4px',
      cursor: 'pointer',
      transition: 'color 200ms',
    }),
    [activeTab],
  );

  if (mode === 'compact') {
    return (
      <div
        style={{
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          fontFamily: 'var(--font)',
        }}
      >
        {/* Tab bar */}
        <div
          style={{
            display: 'flex',
            gap: 2,
            borderBottom: '1px solid var(--border)',
            flexShrink: 0,
          }}
        >
          <button type="button" style={tabStyle('stream')} onClick={() => handleTabClick('stream')}>
            Log
          </button>
          <button
            type="button"
            style={tabStyle('timeline')}
            onClick={() => handleTabClick('timeline')}
          >
            Timeline
          </button>
        </div>

        {/* Content */}
        <div style={{ flex: 1, overflow: 'hidden' }}>
          {activeTab === 'stream' ? (
            <StreamView paused={false} />
          ) : (
            <TimelineView />
          )}
        </div>
      </div>
    );
  }

  // Expanded mode — same layout, more vertical space
  return (
    <div
      style={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        fontFamily: 'var(--font)',
      }}
    >
      <div
        style={{
          display: 'flex',
          gap: 2,
          borderBottom: '1px solid var(--border)',
          flexShrink: 0,
        }}
      >
        <button type="button" style={tabStyle('stream')} onClick={() => handleTabClick('stream')}>
          Log Stream
        </button>
        <button
          type="button"
          style={tabStyle('timeline')}
          onClick={() => handleTabClick('timeline')}
        >
          Turn Timeline
        </button>
      </div>

      <div style={{ flex: 1, overflow: 'hidden' }}>
        {activeTab === 'stream' ? (
          <StreamView paused={false} />
        ) : (
          <TimelineView />
        )}
      </div>
    </div>
  );
}

export default LogPanel;
