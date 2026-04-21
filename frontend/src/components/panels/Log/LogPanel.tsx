/**
 * LogPanel — panel body for log stream + turn timeline.
 * Returns only body content; the Window wrapper supplies chrome via HudPanel.
 *
 * Two-tab HUD panel:
 *   1. Raw Log Stream — live backend log lines with severity colouring.
 *   2. Turn Timeline — Gantt-style waterfall for the last 5 voice turns.
 *
 * SFX: no special SFX (passive display).
 */
import { useCallback, useMemo, useRef, useState, useEffect } from 'react';
import type { CSSProperties, ReactElement } from 'react';
import type { LogLinePayload, PanelMode, TurnTimingPayload } from '../../../types';
import { useLogStream } from '../../../hooks/useLogStream';
import { useTurnTimings } from '../../../hooks/useTurnTimings';
import { LogLine } from './LogLine';
import './LogPanel.css';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface LogPanelProps {
    mode: PanelMode;
}

type TabId = 'stream' | 'timeline';

// ---------------------------------------------------------------------------
// Phase colour constants (accent spectrum — no hardcoded hex that aren't
// token-aligned — these match the design system's accent colour range)
// ---------------------------------------------------------------------------

const PHASE_COLORS: ReadonlyArray<string> = [
    'var(--accent)',
    'var(--accent-bright)',
    'var(--accent-dim)',
    'var(--accent-speak)',
    'var(--text-secondary)',
];

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

    useEffect(() => {
        if (!hovering && !paused && scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [lines, hovering, paused]);

    const visible = useMemo(() => {
        if (lines.length <= VISIBLE_LINES) return lines;
        return lines.slice(lines.length - VISIBLE_LINES);
    }, [lines]);

    return (
        <div className="log-stream">
            <div className="log-toolbar">
                <span className="log-toolbar__count">
                    {lines.length} lines{hovering ? ' — paused' : ''}
                </span>
                <button type="button" className="log-toolbar__clear" onClick={clear}>
                    CLEAR
                </button>
            </div>
            <div
                ref={scrollRef}
                className="log-scroll"
                onMouseEnter={() => setHovering(true)}
                onMouseLeave={() => setHovering(false)}
            >
                {visible.length === 0 ? (
                    <div className="log-empty">Waiting for log stream…</div>
                ) : (
                    visible.map((entry: LogLinePayload, idx: number) => (
                        <LogLine
                            key={`${entry.timestamp}-${idx}-${entry.message.slice(0, 16)}`}
                            entry={entry}
                        />
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

function TurnCard({ turn, index, domainStartMs, domainDurationMs }: TurnCardProps): ReactElement {
    const phases = useMemo(
        () => [
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
        ],
        [turn],
    );

    const totalMs = Math.round(turn.tts_done_ts - turn.audio_end_ts);

    return (
        <div style={{ padding: '4px 6px', borderBottom: '1px solid var(--border)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
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
                <span style={{ fontFamily: 'var(--font)', fontSize: 8, color: 'var(--accent)' }}>
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

function TimelineView(): ReactElement {
    const { turns } = useTurnTimings();

    const { domainDurationMs } = useMemo(() => {
        if (turns.length === 0) return { domainDurationMs: 1 };
        const maxDuration = Math.max(...turns.map((t) => t.tts_done_ts - t.audio_end_ts), 1);
        return { domainDurationMs: maxDuration };
    }, [turns]);

    if (turns.length === 0) {
        return (
            <div className="log-timeline-empty">
                No voice turns yet — speak to JARVIS to populate the timeline.
            </div>
        );
    }

    return (
        <div className="log-timeline">
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

    const tabClass = (tab: TabId): string =>
        `log-tab ${activeTab === tab ? 'log-tab--active' : 'log-tab--inactive'}`;

    const streamLabel = mode === 'compact' ? 'Log' : 'Log Stream';
    const timelineLabel = mode === 'compact' ? 'Timeline' : 'Turn Timeline';

    return (
        <div className="log-panel">
            <div className="log-tabs">
                <button
                    type="button"
                    className={tabClass('stream')}
                    onClick={() => handleTabClick('stream')}
                >
                    {streamLabel}
                </button>
                <button
                    type="button"
                    className={tabClass('timeline')}
                    onClick={() => handleTabClick('timeline')}
                >
                    {timelineLabel}
                </button>
            </div>
            <div className="log-content">
                {activeTab === 'stream' ? <StreamView paused={false} /> : <TimelineView />}
            </div>
        </div>
    );
}

export default LogPanel;
