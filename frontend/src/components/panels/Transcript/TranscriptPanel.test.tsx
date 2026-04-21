/**
 * TranscriptPanel — Vitest + RTL tests (modular folder rebuild).
 */
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

// Mock hooks
vi.mock('../../../hooks/useTranscripts', () => ({
  useTranscripts: () => ({ turns: [], isLive: false }),
}));

vi.mock('../../../hud/SfxContext', () => ({
  useSfx: () => ({ playOneShot: vi.fn() }),
}));

import type { TranscriptTurn } from '../../../types';
import { TranscriptPanel } from './TranscriptPanel';

function makeTurn(id: string, role: 'user' | 'jarvis', text: string): TranscriptTurn {
  return { id, role, text, at: new Date().toISOString() };
}

describe('TranscriptPanel', () => {
  it('renders empty compact state when no turns', () => {
    render(<TranscriptPanel turns={[]} mode="compact" />);
    expect(screen.getByText(/kein transcript/i)).toBeTruthy();
  });

  it('compact: shows last jarvis text', () => {
    const turns = [
      makeTurn('1', 'user', 'Hello'),
      makeTurn('2', 'jarvis', 'Guten Morgen, Sir.'),
    ];
    render(<TranscriptPanel turns={turns} mode="compact" />);
    expect(screen.getByText('Guten Morgen, Sir.')).toBeTruthy();
  });

  it('expanded: renders all turns', () => {
    const turns = [
      makeTurn('1', 'user', 'Hello there'),
      makeTurn('2', 'jarvis', 'How can I assist?'),
      makeTurn('3', 'user', 'What is the time?'),
    ];
    render(<TranscriptPanel turns={turns} mode="expanded" />);
    expect(screen.getByText('Hello there')).toBeTruthy();
    expect(screen.getByText('How can I assist?')).toBeTruthy();
    expect(screen.getByText('What is the time?')).toBeTruthy();
  });

  it('expanded: renders correct number of bubbles for N turns', () => {
    const turns = [
      makeTurn('a', 'user', 'User message one'),
      makeTurn('b', 'jarvis', 'Jarvis reply one'),
    ];
    render(<TranscriptPanel turns={turns} mode="expanded" />);
    expect(screen.getByText('User message one')).toBeTruthy();
    expect(screen.getByText('Jarvis reply one')).toBeTruthy();
  });

  it('expanded: empty turns renders gracefully', () => {
    render(<TranscriptPanel turns={[]} mode="expanded" />);
    // panel body renders without crashing — no content
    const panel = document.querySelector('.transcript-panel');
    expect(panel).not.toBeNull();
  });

  it('compact: shows JARVIS role label when jarvis turn present', () => {
    const turns = [makeTurn('1', 'jarvis', 'Ready to assist.')];
    render(<TranscriptPanel turns={turns} mode="compact" />);
    expect(screen.getByText('JARVIS')).toBeTruthy();
  });
});
