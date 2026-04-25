/**
 * NotificationsPanel — Vitest + RTL tests (feature migration).
 *
 * Dispatches Redux actions directly to bypass RTK Query async pipeline.
 */
import { act, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { installMockWsClient, _mockWsClientImpl } from '@test/mockWsClient';
import { renderWithProviders } from '@test/renderWithProviders';

vi.mock('@core/websocket/wsClient', () => ({ wsClient: _mockWsClientImpl }));
import notificationsReducer, { notificationReceived } from '../../../notificationsSlice';
import { NotificationsPanel } from '../NotificationsPanel';
import type { HudNotification } from '../../../types';

const ws = installMockWsClient();

function render(props?: Partial<Parameters<typeof NotificationsPanel>[0]>) {
    return renderWithProviders(<NotificationsPanel {...props} />, {
        reducers: { notifications: notificationsReducer },
    });
}

const mockNotifications: HudNotification[] = [
    {
        id: 'nt-1',
        severity: 'warning',
        title: 'Meeting in 10 Minutes',
        detail: 'Standup — Platform Team.',
        timestamp: new Date(Date.now() - 30_000).toISOString(),
    },
    {
        id: 'nt-2',
        severity: 'urgent',
        title: 'VIP mail from Elena Vogt',
        detail: 'Subject: Q2 Roadmap.',
        timestamp: new Date(Date.now() - 8 * 60_000).toISOString(),
    },
];

describe('NotificationsPanel — props override (no WS)', () => {
    beforeEach(() => {
        ws.reset();
    });
    afterEach(() => {
        vi.clearAllMocks();
    });

    it('renders notification titles from props', () => {
        render({ notifications: mockNotifications });
        expect(screen.getByText('Meeting in 10 Minutes')).toBeInTheDocument();
        expect(screen.getByText('VIP mail from Elena Vogt')).toBeInTheDocument();
    });

    it('shows empty state when notifications prop is empty', () => {
        render({ notifications: [] });
        expect(screen.getByText(/keine aktiven benachrichtigungen/i)).toBeInTheDocument();
    });

    it('compact: shows latest title and +N badge', () => {
        render({ notifications: mockNotifications, mode: 'compact' });
        expect(screen.getByText('Meeting in 10 Minutes')).toBeInTheDocument();
        expect(screen.getByText('+1')).toBeInTheDocument();
    });
});

describe('NotificationsPanel — live Redux data', () => {
    beforeEach(() => {
        ws.reset();
        vi.useFakeTimers();
    });
    afterEach(() => {
        vi.useRealTimers();
        vi.clearAllMocks();
    });

    it('renders notification from live Redux dispatch', () => {
        const { store } = render({ mode: 'expanded' });
        act(() => {
            store.dispatch(
                notificationReceived({
                    id: 'live-1',
                    severity: 'info',
                    title: 'Live Alert',
                    detail: 'Something happened.',
                    timestamp: new Date().toISOString(),
                }),
            );
        });
        expect(screen.getByText('Live Alert')).toBeInTheDocument();
    });

    it('deduplicates notifications by id', () => {
        const { store } = render({ mode: 'expanded' });
        act(() => {
            store.dispatch(
                notificationReceived({
                    id: 'dup-1',
                    severity: 'info',
                    title: 'Dupe',
                    detail: 'First.',
                    timestamp: new Date().toISOString(),
                }),
            );
            store.dispatch(
                notificationReceived({
                    id: 'dup-1',
                    severity: 'info',
                    title: 'Dupe',
                    detail: 'Second.',
                    timestamp: new Date().toISOString(),
                }),
            );
        });
        const items = screen.getAllByText('Dupe');
        expect(items).toHaveLength(1);
    });

    it('shows unavailable state after 10s with no live data', () => {
        render({ mode: 'expanded' });
        act(() => {
            vi.advanceTimersByTime(10_100);
        });
        expect(screen.getByText(/benachrichtigungen momentan nicht verfügbar/i)).toBeInTheDocument();
    });
});
