import type { TurnTimingPayload } from '../../types';

export interface TurnTimingSummaryProps {
    turns: ReadonlyArray<TurnTimingPayload>;
}

export interface PhaseBarProps {
    label: string;
    startMs: number | null;
    endMs: number | null;
    domainStartMs: number;
    domainDurationMs: number;
    color: string;
}

export interface TurnCardProps {
    turn: TurnTimingPayload;
    index: number;
    domainDurationMs: number;
}
