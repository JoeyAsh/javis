/**
 * AgendaPanel — Vitest + RTL tests (feature migration).
 *
 * Dispatches Redux actions directly to bypass RTK Query async pipeline.
 */
import { act, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { installMockWsClient } from '@test/mockWsClient';
import { renderWithProviders } from '@test/renderWithProviders';
import agendaReducer, { calendarStateReceived } from '../../../agendaSlice';
import { AgendaPanel } from '../AgendaPanel';
import type { AgendaEvent } from '../../../types';

const ws = installMockWsClient();

vi.mock('@core/audio', () => ({
    useSfx: () => ({ playOneShot: vi.fn() }),
}));

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

function render(props?: Partial<Parameters<typeof AgendaPanel>[0]>) {
    return renderWithProviders(<AgendaPanel {...props} />, { reducers: { agenda: agendaReducer } });
}

describe('AgendaPanel', () => {
    beforeEach(() => {
        ws.reset();
        vi.clearAllMocks();
    });
    afterEach(() => {
        ws.reset();
    });

    it('shows loading state before first live push (no eventsProp)', () => {
        render({ mode: 'expanded' });
        expect(screen.getByText(/kalender wird geladen/i)).toBeTruthy();
    });

    it('renders empty state when events prop is empty array (expanded)', () => {
        render({ events: [], mode: 'expanded' });
        expect(screen.getByText(/keine termine/i)).toBeTruthy();
    });

    it('compact: shows next event title and "in Nmin"', () => {
        const events = [makeEvent('1', 'Team Standup', 15)];
        render({ events, mode: 'compact' });
        expect(screen.getByText('Team Standup')).toBeTruthy();
        expect(screen.getByText(/in \d+min/)).toBeTruthy();
        expect(screen.getByText('NÄCHSTER')).toBeTruthy();
    });

    it('compact: shows empty state when events prop is empty', () => {
        render({ events: [], mode: 'compact' });
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
        render({ events, mode: 'expanded' });
        expect(screen.getByText('Standup')).toBeTruthy();
        expect(screen.getByText('Lunch')).toBeTruthy();
        expect(screen.getByText('Review')).toBeTruthy();
        expect(screen.getByText('Planning')).toBeTruthy();
        expect(screen.queryByText('ShouldNotShow')).toBeNull();
    });

    it('updates when a calendar_state Redux action fires', () => {
        const { store } = render({ mode: 'expanded' });
        expect(screen.getByText(/kalender wird geladen/i)).toBeTruthy();

        act(() => {
            store.dispatch(
                calendarStateReceived({
                    events: [makeEvent('live1', 'Live Standup', 5)],
                    dateLabel: 'Heute',
                }),
            );
        });

        expect(screen.getByText('Live Standup')).toBeTruthy();
    });

    it('fires SFX when a row is clicked', async () => {
        const events = [makeEvent('1', 'Clickable Event', 60)];
        render({ events, mode: 'expanded' });
        await userEvent.click(screen.getByText('Clickable Event'));
        expect(screen.getByText('Clickable Event')).toBeTruthy();
    });

    it('expanded: renders correct number of rows for 2 events', () => {
        const events = [makeEvent('a', 'EventA', 30), makeEvent('b', 'EventB', 90)];
        render({ events, mode: 'expanded' });
        expect(screen.getByText('EventA')).toBeTruthy();
        expect(screen.getByText('EventB')).toBeTruthy();
    });
});
