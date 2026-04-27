/**
 * LedgerKindBadge — pill badge for a LedgerKind value.
 * Pure presentational component; no store access.
 */
import type { ReactElement } from 'react';
import type { LedgerKindBadgeProps } from './LedgerKindBadge.types';
import type { LedgerKind } from '../../types';

const KIND_CLASSES: Record<LedgerKind, string> = {
    tts_emitted:      'bg-cyan-900/40 text-cyan-300 border border-cyan-700/50',
    mcp_call:         'bg-violet-900/40 text-violet-300 border border-violet-700/50',
    wake_word:        'bg-emerald-900/40 text-emerald-300 border border-emerald-700/50',
    orb_state:        'bg-sky-900/40 text-sky-300 border border-sky-700/50',
    panel_open:       'bg-slate-700/50 text-slate-300 border border-slate-600/50',
    panel_close:      'bg-slate-800/50 text-slate-400 border border-slate-700/50',
    barge_in:         'bg-orange-900/40 text-orange-300 border border-orange-700/50',
    voice_turn_start: 'bg-green-900/40 text-green-300 border border-green-700/50',
    voice_turn_end:   'bg-teal-900/40 text-teal-300 border border-teal-700/50',
    error:            'bg-red-900/40 text-red-400 border border-red-700/50',
};

const KIND_GLYPH: Record<LedgerKind, string> = {
    tts_emitted:      '♪',
    mcp_call:         '⚙',
    wake_word:        '◉',
    orb_state:        '◎',
    panel_open:       '▤',
    panel_close:      '▣',
    barge_in:         '⚡',
    voice_turn_start: '▶',
    voice_turn_end:   '■',
    error:            '✕',
};

export function LedgerKindBadge({ kind }: LedgerKindBadgeProps): ReactElement {
    return (
        <span
            className={`inline-flex items-center gap-0.5 text-[8px] px-1.5 py-0.5 rounded-sm font-mono shrink-0 ${KIND_CLASSES[kind]}`}
        >
            <span>{KIND_GLYPH[kind]}</span>
            <span>{kind}</span>
        </span>
    );
}

export default LedgerKindBadge;
