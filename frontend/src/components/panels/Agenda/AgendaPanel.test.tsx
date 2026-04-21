/**
 * AgendaPanel — Vitest + RTL tests (modular folder rebuild).
 *
 * All WS subscriptions are intercepted via vi.mock. Tests cover:
 *   - Loading state before first live push
 *   - Empty event list
 *   - Compact mode with next event
 *   - Expanded mode renders up to 4 events
 *   - Live calendar_state WS message triggers re-render
 *   - SFX select fires on row click
 */
import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { CalendarStateListener } from '../../../hooks/useWebSocket';

// Mock WS
let capturedCalendarStateListener: CalendarStateListener | null = null;
vi.mock('../../../hooks/useWebSocket', () => ({
    subscribeCalendarStateStream: vi.fn((listener: CalendarStateListener) => {
        capturedCalendarStateListener = listener;
        return () => {
            capturedCalendarStateListener = null;
        };
    }),
}));

// Mock SfxContext
const mockPlayOneShot = vi.fn();
vi.mock('../../../hud/SfxContext', () => ({
    useSfx: () => ({ playOneShot: mockPlayOneShot }),
}));

import type { AgendaEvent } from '../../../types';
import { AgendaPanel } from './AgendaPanel';

function makeEvent(id: string, title: string, offsetMinutes = 30): AgendaEvent {
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

describe('AgendaPanel', () => {
    beforeEach(() => {
        capturedCalendarStateListener = null;
        mockPlayOneShot.mockClear();
        vi.clearAllMocks();
    });

    afterEach(() => {
        capturedCalendarStateListener = null;
    });

    it('shows loading state before first live push (no prop)', () => {
        render(<AgendaPanel mode="expanded" />);
        expect(screen.getByText(/kalender wird geladen/i)).toBeTruthy();
    });

    it('renders empty state when events prop is empty array (expanded)', () => {
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

    it('compact: shows empty state when events prop is empty', () => {
        render(<AgendaPanel events={[]} mode="compact" />);
        expect(screen.getByText(/keine termine heute/i)).toBeTruthy();
    });

    it('expanded: renders up to 4 events', () => {
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
        expect(screen.getByText(/kalender wird geladen/i)).toBeTruthy();

        await act(async () => {
            capturedCalendarStateListener?.({
                events: [makeEvent('live1', 'Live Standup', 5)],
                dateLabel: 'Heute',
            });
        });

        expect(screen.getByText('Live Standup')).toBeTruthy();
    });

    it('fires select SFX when a row is clicked', async () => {
        const events = [makeEvent('1', 'Clickable Event', 60)];
        render(<AgendaPanel events={events} mode="expanded" />);
        await userEvent.click(screen.getByText('Clickable Event'));
        expect(mockPlayOneShot).toHaveBeenCalledWith('click');
    });

    it('expanded: renders correct number of rows for 2 events', () => {
        const events = [makeEvent('a', 'EventA', 30), makeEvent('b', 'EventB', 90)];
        render(<AgendaPanel events={events} mode="expanded" />);
        expect(screen.getByText('EventA')).toBeTruthy();
        expect(screen.getByText('EventB')).toBeTruthy();
    });
});
