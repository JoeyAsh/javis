import { useMemo } from 'react';
import type { CSSProperties, ReactElement } from 'react';
import type { TurnTimingSummaryProps, PhaseBarProps, TurnCardProps } from './TurnTimingSummary.types';
import styles from './TurnTimingSummary.module.css';

// Phase colour constants (accent spectrum, no hardcoded hex outside token system)
const PHASE_COLORS: ReadonlyArray<string> = [
    'var(--accent)',
    'var(--accent-bright)',
    'var(--accent-dim)',
    'var(--accent-speak)',
    'var(--text-secondary)',
];

// ---------------------------------------------------------------------------
// Phase bar
// ---------------------------------------------------------------------------

function PhaseBar({
    label,
    startMs,
    endMs,
    domainStartMs,
    domainDurationMs,
    color,
}: PhaseBarProps): ReactElement | null {
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
    };

    return (
        <div className={styles.phaseRow}>
            <span className={styles.phaseLabel}>{label}</span>
            <div className={styles.phaseTrack}>
                <div style={barStyle} title={`${label}: ${duration} ms`} />
            </div>
            <span className={styles.phaseDuration}>{duration}ms</span>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Turn card
// ---------------------------------------------------------------------------

function TurnCard({ turn, index, domainDurationMs }: TurnCardProps): ReactElement {
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
        <div className={styles.turnCard}>
            <div className={styles.turnHeader}>
                <span className={styles.turnId}>
                    TURN {index + 1} · {turn.turn_id}
                </span>
                <span className={styles.turnTotal}>{totalMs}ms total</span>
            </div>
            {phases.map((phase) => (
                <PhaseBar
                    key={phase.label}
                    label={phase.label}
                    startMs={phase.startMs}
                    endMs={phase.endMs}
                    domainStartMs={turn.audio_end_ts}
                    domainDurationMs={domainDurationMs}
                    color={phase.color}
                />
            ))}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Public component
// ---------------------------------------------------------------------------

export function TurnTimingSummary({ turns }: TurnTimingSummaryProps): ReactElement {
    const domainDurationMs = useMemo(() => {
        if (turns.length === 0) return 1;
        return Math.max(...turns.map((t) => t.tts_done_ts - t.audio_end_ts), 1);
    }, [turns]);

    if (turns.length === 0) {
        return (
            <div className={styles.empty}>
                No voice turns yet — speak to JARVIS to populate the timeline.
            </div>
        );
    }

    return (
        <div className={styles.timeline}>
            {turns.map((turn, i) => (
                <TurnCard
                    key={turn.turn_id}
                    turn={turn}
                    index={i}
                    domainDurationMs={domainDurationMs}
                />
            ))}
        </div>
    );
}

export default TurnTimingSummary;
