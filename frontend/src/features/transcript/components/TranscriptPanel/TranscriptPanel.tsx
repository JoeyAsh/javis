/**
 * TranscriptPanel — panel body for conversation turns.
 * Data comes from the Redux transcript slice via useTranscript hook.
 * No mock-fallback in production — empty state shows when no live data.
 */
import { useEffect, useMemo, useRef } from 'react';
import type { ReactElement } from 'react';
import { useTranscript } from '../../hooks/useTranscript';
import { TranscriptEntry } from '../TranscriptEntry';
import { ThinkingDots } from '../ThinkingDots';
import type { TranscriptTurn } from '../../types';
import type { TranscriptPanelProps } from './TranscriptPanel.types';
import styles from './TranscriptPanel.module.css';

// ---- Compact mode ----

function TranscriptCompact({ turns }: { turns: TranscriptTurn[] }): ReactElement {
    const lastJarvis = useMemo(
        () => [...turns].reverse().find((t) => t.role === 'jarvis'),
        [turns],
    );

    if (!lastJarvis) {
        return (
            <div className={styles.compact}>
                <span className={styles.empty}>Kein Transcript</span>
            </div>
        );
    }

    const d = new Date(lastJarvis.at);
    const time = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;

    return (
        <div className={styles.compact}>
            <div className={styles.compactHeader}>
                <span className={styles.compactRole}>JARVIS</span>
                <span className={styles.compactTime}>{time}</span>
            </div>
            <div className={styles.compactText} title={lastJarvis.text}>
                {lastJarvis.text}
            </div>
        </div>
    );
}

// ---- Expanded mode ----

type TranscriptExpandedProps = {
    turns: TranscriptTurn[];
    orbState: NonNullable<TranscriptPanelProps['orbState']>;
};

function TranscriptExpanded({ turns, orbState }: TranscriptExpandedProps): ReactElement {
    const bottomRef = useRef<HTMLDivElement | null>(null);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }, [turns, orbState]);

    return (
        <div className={styles.panel}>
            {turns.map((t) => (
                <TranscriptEntry key={t.id} turn={t} />
            ))}
            {orbState === 'thinking' && <ThinkingDots />}
            <div ref={bottomRef} />
        </div>
    );
}

// ---- Main export ----

/**
 * TranscriptPanel body — conversation turns with user/jarvis bubbles.
 * When orbState is 'thinking', shows the ThinkingDots indicator.
 * Accepts optional `turns` prop for testing (skips live data).
 */
export function TranscriptPanel({
    turns: turnsProp,
    mode = 'expanded',
    orbState = 'idle',
}: TranscriptPanelProps): ReactElement {
    const { turns: liveTurns } = useTranscript();

    // Prop override takes priority (used in tests). Otherwise use live Redux turns.
    const effectiveTurns: TranscriptTurn[] = turnsProp !== undefined ? turnsProp : liveTurns;

    return mode === 'compact' ? (
        <TranscriptCompact turns={effectiveTurns} />
    ) : (
        <TranscriptExpanded turns={effectiveTurns} orbState={orbState} />
    );
}

export default TranscriptPanel;
