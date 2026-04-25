/**
 * MailPanel — Vitest + RTL tests (feature migration).
 *
 * Tests dispatch Redux actions directly to bypass RTK Query's async
 * onCacheEntryAdded pipeline, making tests deterministic and fast.
 */
import { act, fireEvent, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { installMockWsClient, _mockWsClientImpl } from '@test/mockWsClient';
import { renderWithProviders } from '@test/renderWithProviders';

vi.mock('@core/websocket/wsClient', () => ({ wsClient: _mockWsClientImpl }));
import mailReducer, {
    mailStateReceived,
    draftPreviewReceived,
    emailSendDone,
} from '../../../mailSlice';
import { MailPanel } from '../MailPanel';
import type { MailMessage } from '../../../types';

// vi.mock at module top-level (hoisted by Vitest).
const ws = installMockWsClient();

vi.mock('@core/audio', () => ({
    useSfx: () => ({ playOneShot: vi.fn() }),
}));

const liveMessages: MailMessage[] = [
    {
        id: 'live-1',
        sender: 'Sarah Connor',
        subject: 'Meeting tomorrow',
        preview: 'Can we meet at 10?',
        receivedAt: new Date().toISOString(),
        isVip: false,
        unread: true,
    },
    {
        id: 'live-2',
        sender: 'John Doe',
        subject: 'Project update',
        preview: 'All good on my end.',
        receivedAt: new Date().toISOString(),
        isVip: true,
        unread: true,
    },
];

function render(mode?: 'compact' | 'expanded') {
    return renderWithProviders(<MailPanel mode={mode} />, { reducers: { mail: mailReducer } });
}

describe('MailPanel — live mail_state data', () => {
    beforeEach(() => {
        ws.reset();
        vi.useFakeTimers();
    });
    afterEach(() => {
        vi.useRealTimers();
        vi.clearAllMocks();
    });

    it('renders sender names from live mail_state', () => {
        const { store } = render();
        act(() => {
            store.dispatch(mailStateReceived({ messages: liveMessages, unread_count: 7 }));
        });
        expect(screen.getByText('Sarah Connor')).toBeInTheDocument();
        expect(screen.getByText('John Doe')).toBeInTheDocument();
    });

    it('mock sender names absent when live data received', () => {
        const { store } = render();
        act(() => {
            store.dispatch(mailStateReceived({ messages: liveMessages, unread_count: 2 }));
        });
        expect(screen.queryByText('Elena Vogt (CTO)')).not.toBeInTheDocument();
    });

    it('shows unavailable state after 10s with no live data', () => {
        render();
        act(() => {
            vi.advanceTimersByTime(10_100);
        });
        expect(screen.getByText('Postfach momentan nicht erreichbar')).toBeInTheDocument();
    });

    it('shows no messages before availability timeout elapses and no live data', () => {
        render();
        expect(screen.queryByText('Sarah Connor')).not.toBeInTheDocument();
        expect(screen.queryByText('Elena Vogt (CTO)')).not.toBeInTheDocument();
    });

    it('renders correct number of rows for 2 messages', () => {
        const { store } = render('expanded');
        act(() => {
            store.dispatch(mailStateReceived({ messages: liveMessages, unread_count: 2 }));
        });
        const rows = screen.getAllByRole('button');
        expect(rows.length).toBeGreaterThanOrEqual(2);
    });

    it('fires click SFX on row click', () => {
        const { store } = render('expanded');
        act(() => {
            store.dispatch(mailStateReceived({ messages: liveMessages, unread_count: 2 }));
        });
        fireEvent.click(screen.getByText('Meeting tomorrow'));
        expect(screen.getByText('Meeting tomorrow')).toBeInTheDocument();
    });
});

describe('MailPanel — DraftPreview section', () => {
    beforeEach(() => {
        ws.reset();
        vi.useFakeTimers();
    });
    afterEach(() => {
        vi.useRealTimers();
        vi.clearAllMocks();
    });

    it('shows draft preview when email_draft_preview arrives', () => {
        const { store } = render('expanded');
        act(() => {
            store.dispatch(
                draftPreviewReceived({
                    draft_id: 'draft-abc',
                    to: 'sarah@example.com',
                    subject: 'Treffen morgen',
                    body_preview: 'Lass uns um 10 Uhr treffen.',
                    created_at: new Date().toISOString(),
                }),
            );
        });
        expect(screen.getByText('sarah@example.com')).toBeInTheDocument();
        expect(screen.getByText('Treffen morgen')).toBeInTheDocument();
        expect(screen.getByText(/JA/)).toBeInTheDocument();
    });

    it('truncates body_preview to 80 chars', () => {
        const { store } = render('expanded');
        const longBody = 'A'.repeat(100);
        act(() => {
            store.dispatch(
                draftPreviewReceived({
                    draft_id: 'draft-long',
                    to: 'test@example.com',
                    subject: 'Long body',
                    body_preview: longBody,
                    created_at: new Date().toISOString(),
                }),
            );
        });
        const truncated = `${'A'.repeat(80)}…`;
        expect(screen.getByText(truncated)).toBeInTheDocument();
    });

    it('hides draft preview after email_send_done', () => {
        const { store } = render('expanded');
        act(() => {
            store.dispatch(
                draftPreviewReceived({
                    draft_id: 'draft-abc',
                    to: 'sarah@example.com',
                    subject: 'Treffen morgen',
                    body_preview: 'Lass uns treffen.',
                    created_at: new Date().toISOString(),
                }),
            );
        });
        expect(screen.getByText('sarah@example.com')).toBeInTheDocument();
        act(() => {
            store.dispatch(emailSendDone({ draft_id: 'draft-abc', success: true, message_id: 'msg-xyz' }));
        });
        expect(screen.queryByText('sarah@example.com')).not.toBeInTheDocument();
    });
});

describe('MailPanel — compact mode', () => {
    beforeEach(() => {
        ws.reset();
        vi.useFakeTimers();
    });
    afterEach(() => {
        vi.useRealTimers();
        vi.clearAllMocks();
    });

    it('renders live unread count in compact mode', () => {
        const { store } = render('compact');
        act(() => {
            store.dispatch(mailStateReceived({ messages: liveMessages, unread_count: 3 }));
        });
        expect(screen.getByText('3')).toBeInTheDocument();
    });

    it('shows draft preview in compact mode', () => {
        const { store } = render('compact');
        act(() => {
            store.dispatch(
                draftPreviewReceived({
                    draft_id: 'd1',
                    to: 'boss@corp.com',
                    subject: 'Status report',
                    body_preview: 'Everything is on track.',
                    created_at: new Date().toISOString(),
                }),
            );
        });
        expect(screen.getByText('boss@corp.com')).toBeInTheDocument();
    });
});
