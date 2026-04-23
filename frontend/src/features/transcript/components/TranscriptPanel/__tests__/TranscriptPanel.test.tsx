/**
 * TranscriptPanel — Vitest + RTL tests (feature migration).
 *
 * Dispatches Redux actions directly to bypass RTK Query async pipeline.
 * scrollIntoView is stubbed because jsdom doesn't implement it.
 */
import { act, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { installMockWsClient } from '@test/mockWsClient';
import { renderWithProviders } from '@test/renderWithProviders';
import transcriptReducer, { transcriptReceived } from '../../../transcriptSlice';
import { TranscriptPanel } from '../TranscriptPanel';
import type { TranscriptTurn } from '../../../types';

const ws = installMockWsClient();

// jsdom doesn't implement scrollIntoView — stub it.
window.HTMLElement.prototype.scrollIntoView = vi.fn();

function makeTurn(id: string, role: 'user' | 'jarvis', text: string): TranscriptTurn {
    return { id, role, text, at: new Date().toISOString() };
}

function render(props?: Partial<Parameters<typeof TranscriptPanel>[0]>) {
    return renderWithProviders(<TranscriptPanel {...props} />, {
        reducers: { transcript: transcriptReducer },
    });
}

describe('TranscriptPanel', () => {
    beforeEach(() => {
        ws.reset();
        vi.clearAllMocks();
    });
    afterEach(() => {
        ws.reset();
    });

    it('renders empty compact state when no turns', () => {
        render({ turns: [], mode: 'compact' });
        expect(screen.getByText(/kein transcript/i)).toBeTruthy();
    });

    it('compact: shows last jarvis text', () => {
        const turns = [
            makeTurn('1', 'user', 'Hello'),
            makeTurn('2', 'jarvis', 'Guten Morgen, Sir.'),
        ];
        render({ turns, mode: 'compact' });
        expect(screen.getByText('Guten Morgen, Sir.')).toBeTruthy();
    });

    it('compact: shows JARVIS role label when jarvis turn present', () => {
        const turns = [makeTurn('1', 'jarvis', 'Ready to assist.')];
        render({ turns, mode: 'compact' });
        expect(screen.getByText('JARVIS')).toBeTruthy();
    });

    it('expanded: renders all turns', () => {
        const turns = [
            makeTurn('1', 'user', 'Hello there'),
            makeTurn('2', 'jarvis', 'How can I assist?'),
            makeTurn('3', 'user', 'What is the time?'),
        ];
        render({ turns, mode: 'expanded' });
        expect(screen.getByText('Hello there')).toBeTruthy();
        expect(screen.getByText('How can I assist?')).toBeTruthy();
        expect(screen.getByText('What is the time?')).toBeTruthy();
    });

    it('expanded: empty turns renders without crash', () => {
        render({ turns: [], mode: 'expanded' });
        expect(document.querySelector('[class*="panel"]')).not.toBeNull();
    });

    it('expanded: shows ThinkingDots when orbState is thinking', () => {
        render({ turns: [], mode: 'expanded', orbState: 'thinking' });
        expect(document.querySelector('[class*="dot"]')).not.toBeNull();
    });

    it('live Redux dispatch appears in expanded panel', () => {
        const { store } = render({ mode: 'expanded' });
        act(() => {
            store.dispatch(transcriptReceived({ role: 'jarvis', text: 'Live response from JARVIS.' }));
        });
        expect(screen.getByText('Live response from JARVIS.')).toBeTruthy();
    });
});
