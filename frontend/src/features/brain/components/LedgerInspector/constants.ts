import type { LedgerKind } from '../../types';

/** All valid LedgerKind values in display order. */
export const ALL_KINDS: LedgerKind[] = [
    'wake_word',
    'voice_turn_start',
    'voice_turn_end',
    'barge_in',
    'tts_emitted',
    'mcp_call',
    'orb_state',
    'panel_open',
    'panel_close',
    'error',
];

/** Time-range filter options: label → lookback in milliseconds (null = all time). */
export const TIME_RANGES: Array<{ label: string; ms: number | null }> = [
    { label: 'all',   ms: null },
    { label: '1h',    ms: 60 * 60 * 1000 },
    { label: 'today', ms: null }, // computed at runtime — see LedgerFilterRow
];
