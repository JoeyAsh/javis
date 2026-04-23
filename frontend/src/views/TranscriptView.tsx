/**
 * TranscriptView — conversation transcript panel content.
 *
 * Replaces legacy components/panels/Transcript/TranscriptPanel.tsx.
 * Uses lib Mono, Label for display.
 */
import { useEffect, useMemo, useRef } from 'react';
import type { CSSProperties, ReactElement } from 'react';
import { Label, Mono } from '../lib';
import { transcriptMock } from '../mock/transcriptMock';
import { useTranscripts } from '../hooks/useTranscripts';
import type { AppOrbState, TranscriptTurn, PanelMode } from '../types';
import './TranscriptView.css';

export interface TranscriptViewProps {
    turns?: TranscriptTurn[];
    mode?: PanelMode;
    orbState?: AppOrbState;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function formatTime(iso: string): string {
    const d = new Date(iso);
    return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

// ── Entry sub-component ──────────────────────────────────────────────────────

function TranscriptEntry({ turn }: { turn: TranscriptTurn }): ReactElement {
    const isUser = turn.role === 'user';
    const rowClass = `tv-turn ${isUser ? 'tv-turn--user' : 'tv-turn--jarvis'}`;
    const bubbleClass = isUser ? 'tv-bubble--user' : 'tv-bubble--jarvis';

    return (
        <div className={rowClass}>
            <div className="tv-block">
                <div className="tv-meta">
                    {!isUser && (
                        <Label className="tv-meta__role">J.</Label>
                    )}
                    {isUser ? 'You ' : ''}
                    <Mono size="xs" muted>{formatTime(turn.at)}</Mono>
                </div>
                <div className={bubbleClass}>{turn.text}</div>
            </div>
        </div>
    );
}

// ── Thinking dots ────────────────────────────────────────────────────────────

const dotStyle: CSSProperties = {
    width: 4,
    height: 4,
    background: 'var(--accent)',
    borderRadius: '50%',
    display: 'inline-block',
};

function ThinkingDots(): ReactElement {
    return (
        <div className="tv-turn tv-turn--jarvis">
            <div className="tv-block">
                <div className="tv-meta">
                    <Label className="tv-meta__role">J.</Label>
                    <Mono size="xs" muted>…</Mono>
                </div>
                <div className="tv-bubble--jarvis">
                    <span style={{ display: 'inline-flex', gap: 3 }}>
                        <i style={{ ...dotStyle, animation: 'blink 1.2s ease-in-out infinite' }} />
                        <i style={{ ...dotStyle, animation: 'blink 1.2s ease-in-out infinite 0.2s' }} />
                        <i style={{ ...dotStyle, animation: 'blink 1.2s ease-in-out infinite 0.4s' }} />
                    </span>
                </div>
            </div>
        </div>
    );
}

// ── Compact ──────────────────────────────────────────────────────────────────

function TranscriptCompact({ turns }: { turns: TranscriptTurn[] }): ReactElement {
    const lastJarvis = useMemo(
        () => [...turns].reverse().find((t) => t.role === 'jarvis'),
        [turns],
    );
    if (!lastJarvis) {
        return (
            <div className="tv-compact">
                <Mono size="sm" muted>Kein Transcript</Mono>
            </div>
        );
    }
    const time = formatTime(lastJarvis.at);
    return (
        <div className="tv-compact">
            <div className="tv-compact__hdr">
                <Label>JARVIS</Label>
                <Mono size="xs" muted>{time}</Mono>
            </div>
            <Mono size="sm" className="tv-compact__text">{lastJarvis.text}</Mono>
        </div>
    );
}

// ── Expanded ─────────────────────────────────────────────────────────────────

function TranscriptExpanded({
    turns,
    orbState,
}: {
    turns: TranscriptTurn[];
    orbState: AppOrbState;
}): ReactElement {
    const bottomRef = useRef<HTMLDivElement | null>(null);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }, [turns, orbState]);

    return (
        <div className="tv-expanded">
            {turns.map((t) => (
                <TranscriptEntry key={t.id} turn={t} />
            ))}
            {orbState === 'thinking' && <ThinkingDots />}
            <div ref={bottomRef} />
        </div>
    );
}

// ── Entry point ──────────────────────────────────────────────────────────────

export function TranscriptView({
    turns,
    mode = 'expanded',
    orbState = 'idle',
}: TranscriptViewProps): ReactElement {
    const { turns: liveTurns, isLive } = useTranscripts();
    const effectiveTurns: TranscriptTurn[] =
        turns !== undefined ? turns : isLive ? liveTurns : transcriptMock;

    return mode === 'compact' ? (
        <TranscriptCompact turns={effectiveTurns} />
    ) : (
        <TranscriptExpanded turns={effectiveTurns} orbState={orbState} />
    );
}

export default TranscriptView;

