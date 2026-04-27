// === FILE: frontend/src/features/brain/__tests__/LedgerKindBadge.test.tsx ===
/**
 * Tests for LedgerKindBadge — pure props test.
 * Covers every LedgerKind value renders its expected glyph and label text.
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { LedgerKindBadge } from '../components/LedgerKindBadge/LedgerKindBadge';
import type { LedgerKind } from '../types';

// The expected glyphs as defined in LedgerKindBadge.tsx
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

const ALL_KINDS: LedgerKind[] = [
    'tts_emitted',
    'mcp_call',
    'wake_word',
    'orb_state',
    'panel_open',
    'panel_close',
    'barge_in',
    'voice_turn_start',
    'voice_turn_end',
    'error',
];

describe('LedgerKindBadge', () => {
    it.each(ALL_KINDS)('renders kind="%s" with its glyph', (kind) => {
        const { container } = render(<LedgerKindBadge kind={kind} />);

        // The kind label text is rendered.
        expect(container.textContent).toContain(kind);

        // The glyph is rendered.
        const expectedGlyph = KIND_GLYPH[kind];
        expect(container.textContent).toContain(expectedGlyph);
    });

    it('renders a span element', () => {
        const { container } = render(<LedgerKindBadge kind="tts_emitted" />);
        const span = container.querySelector('span');
        expect(span).not.toBeNull();
    });

    it('renders the tts_emitted badge with musical note glyph', () => {
        const { container } = render(<LedgerKindBadge kind="tts_emitted" />);
        expect(container.textContent).toContain('♪');
        expect(container.textContent).toContain('tts_emitted');
    });

    it('renders the error badge with X glyph', () => {
        const { container } = render(<LedgerKindBadge kind="error" />);
        expect(container.textContent).toContain('✕');
        expect(container.textContent).toContain('error');
    });

    it('renders the barge_in badge with lightning glyph', () => {
        const { container } = render(<LedgerKindBadge kind="barge_in" />);
        expect(container.textContent).toContain('⚡');
        expect(container.textContent).toContain('barge_in');
    });

    it('renders voice_turn_start badge with play glyph', () => {
        const { container } = render(<LedgerKindBadge kind="voice_turn_start" />);
        expect(container.textContent).toContain('▶');
        expect(container.textContent).toContain('voice_turn_start');
    });

    it('renders voice_turn_end badge with stop glyph', () => {
        const { container } = render(<LedgerKindBadge kind="voice_turn_end" />);
        expect(container.textContent).toContain('■');
        expect(container.textContent).toContain('voice_turn_end');
    });

    it('renders wake_word badge with filled-circle glyph', () => {
        const { container } = render(<LedgerKindBadge kind="wake_word" />);
        expect(container.textContent).toContain('◉');
        expect(container.textContent).toContain('wake_word');
    });

    it('renders mcp_call badge with gear glyph', () => {
        const { container } = render(<LedgerKindBadge kind="mcp_call" />);
        expect(container.textContent).toContain('⚙');
        expect(container.textContent).toContain('mcp_call');
    });
});
