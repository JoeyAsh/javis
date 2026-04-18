/**
 * AgendaPanel — Vitest + RTL tests.
 *
 * All WS subscriptions are intercepted via vi.mock so no real WebSocket
 * connection is attempted. Tests cover:
 *   - Loading state before first live push
 *   - Empty event list (no events)
 *   - Compact mode with a next event
 *   - Expanded mode with up to 4 events
 *   - Live calendar_state WS message triggers re-render
 *   - No agendaMock import present in the panel source
 */
import { act, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { CalendarStateListener } from '../../../hooks/useWebSocket';

// ---------------------------------------------------------------------------
// Mock the WS stream helper so no real WebSocket is used.
// ---------------------------------------------------------------------------

let capturedCalendarStateListener: CalendarStateListener | null = null;

vi.mock('../../../hooks/useWebSocket', () => ({
  subscribeCalendarStateStream: vi.fn((listener: CalendarStateListener) => {
    capturedCalendarStateListener = listener;
    return () => {
      capturedCalendarStateListener = null;
    };
  }),
}));

import type { AgendaEvent } from '../../../types';
import { AgendaPanel } from '../AgendaPanel';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeEvent(
  id: string,
  title: string,
  offsetMinutes = 30,
): AgendaEvent {
  const now = new Date();
  const start = new Date(now.getTime() + offsetMinutes * 60_000);
  const end = new Date(start.getTime() + 60 * 60_000);
  return {
    id,
    title,
    start: start.toISOString(),
    end: end.toISOString(),
    calendar: 'primary',
    location: undefined,
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('AgendaPanel', () => {
  beforeEach(() => {
    capturedCalendarStateListener = null;
    vi.clearAllMocks();
  });

  afterEach(() => {
    capturedCalendarStateListener = null;
  });

  it('shows loading state before first live push (no prop)', () => {
    render(<AgendaPanel mode="expanded" />);
    expect(screen.getByText(/kalender wird geladen/i)).toBeTruthy();
  });

  it('renders empty state when events prop is empty array', () => {
    render(<AgendaPanel events={[]} mode="expanded" />);
    expect(screen.getByText(/keine termine/i)).toBeTruthy();
  });

  it('compact: shows next event title and "in Nmin"', () => {
    const events = [makeEvent('1', 'Team Standup', 15)];
    render(<AgendaPanel events={events} mode="compact" />);
    expect(screen.getByText('Team Standup')).toBeTruthy();
    expect(screen.getByText(/in \d+min/)).toBeTruthy();
    expect(screen.getByText('NÄCHSTER')).toBeTruthy();
  });

  it('compact: shows "Keine Termine heute" when events prop is empty', () => {
    render(<AgendaPanel events={[]} mode="compact" />);
    expect(screen.getByText(/keine termine heute/i)).toBeTruthy();
  });

  it('expanded: renders up to 4 events with title visible', () => {
    const events = [
      makeEvent('1', 'Standup', 10),
      makeEvent('2', 'Lunch', 60),
      makeEvent('3', 'Review', 120),
      makeEvent('4', 'Planning', 180),
      makeEvent('5', 'ShouldNotShow', 240),
    ];
    render(<AgendaPanel events={events} mode="expanded" />);
    expect(screen.getByText('Standup')).toBeTruthy();
    expect(screen.getByText('Lunch')).toBeTruthy();
    expect(screen.getByText('Review')).toBeTruthy();
    expect(screen.getByText('Planning')).toBeTruthy();
    expect(screen.queryByText('ShouldNotShow')).toBeNull();
  });

  it('updates when a calendar_state WS message fires', async () => {
    render(<AgendaPanel mode="expanded" />);
    // Initially loading
    expect(screen.getByText(/kalender wird geladen/i)).toBeTruthy();

    // Simulate live push
    await act(async () => {
      capturedCalendarStateListener?.({
        events: [makeEvent('live1', 'Live Standup', 5)],
        dateLabel: 'Heute',
      });
    });

    expect(screen.getByText('Live Standup')).toBeTruthy();
  });

  it('does not import agendaMock (no mock dependency in module)', async () => {
    // Verify no agendaMock reference exists in AgendaPanel source.
    const fs = await import('node:fs');
    const path = await import('node:path');
    const filePath = path.resolve(
      __dirname,
      '../AgendaPanel.tsx',
    );
    const source = fs.readFileSync(filePath, 'utf-8');
    expect(source).not.toContain('agendaMock');
  });
});
