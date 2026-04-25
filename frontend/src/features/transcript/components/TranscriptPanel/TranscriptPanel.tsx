/**
 * TranscriptPanel — panel body for conversation turns.
 * Data comes from the Redux transcript slice via useTranscript hook.
 * No mock-fallback in production — empty state shows when no live data.
 */
import type { ReactElement } from 'react';
import { useTranscript } from '../../hooks/useTranscript';
import { TranscriptCompact } from './TranscriptCompact';
import { TranscriptExpanded } from './TranscriptExpanded';
import type { TranscriptTurn } from '../../types';
import type { TranscriptPanelProps } from './TranscriptPanel.types';

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
