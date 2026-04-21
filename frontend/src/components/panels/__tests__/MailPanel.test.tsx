/**
 * MailPanel — Vitest + RTL tests.
 *
 * All WS subscriptions are intercepted via vi.mock so no real WebSocket
 * connection is attempted. Tests cover:
 *   - Renders live unread count + senders from mail_state data
 *   - Shows DraftPreview section when email_draft_preview arrives
 *   - Renders the empty / grace-period state (no mock data within 2 s)
 */
import { act, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// ---------------------------------------------------------------------------
// Mock the WS subscription helpers so no real network is used.
// We capture the registered listeners and call them manually in tests.
// ---------------------------------------------------------------------------

import type {
  EmailDraftPreviewListener,
  EmailSendDoneListener,
  MailStateListener,
} from '../../../hooks/useWebSocket';

let capturedMailStateListener: MailStateListener | null = null;
let capturedDraftPreviewListener: EmailDraftPreviewListener | null = null;
let capturedSendDoneListener: EmailSendDoneListener | null = null;

vi.mock('../../../hooks/useWebSocket', () => ({
  subscribeMailStateStream: vi.fn((listener: MailStateListener) => {
    capturedMailStateListener = listener;
    return () => {
      capturedMailStateListener = null;
    };
  }),
  subscribeEmailDraftPreviewStream: vi.fn((listener: EmailDraftPreviewListener) => {
    capturedDraftPreviewListener = listener;
    return () => {
      capturedDraftPreviewListener = null;
    };
  }),
  subscribeEmailSendDoneStream: vi.fn((listener: EmailSendDoneListener) => {
    capturedSendDoneListener = listener;
    return () => {
      capturedSendDoneListener = null;
    };
  }),
}));

// Import after mocking
import { MailPanel } from '../Mail';
import type { MailMessage } from '../../../types';

// ---------------------------------------------------------------------------
// Test data
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderPanel(mode: 'compact' | 'expanded' = 'expanded') {
  return render(<MailPanel mode={mode} />);
}

// ---------------------------------------------------------------------------
// Test suites
// ---------------------------------------------------------------------------

describe('MailPanel — live mail_state data', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    capturedMailStateListener = null;
    capturedDraftPreviewListener = null;
    capturedSendDoneListener = null;
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it('renders unread count and sender names from live mail_state payload', async () => {
    renderPanel();

    act(() => {
      capturedMailStateListener?.({
        messages: liveMessages,
        unread_count: 7,
      });
    });

    // Unread count
    expect(screen.getByText('7')).toBeInTheDocument();
    // Senders
    expect(screen.getByText('Sarah Connor')).toBeInTheDocument();
    expect(screen.getByText('John Doe')).toBeInTheDocument();
  });

  it('mock-data sender names are absent when live data has been received', async () => {
    renderPanel();

    act(() => {
      capturedMailStateListener?.({
        messages: liveMessages,
        unread_count: 2,
      });
    });

    // Mock senders from mailMock.ts — must not appear
    expect(screen.queryByText('Elena Vogt (CTO)')).not.toBeInTheDocument();
    expect(screen.queryByText('Marco Reinhardt')).not.toBeInTheDocument();
  });

  it('falls back to mock data after 2 s grace period with no mail_state', () => {
    renderPanel();

    // Grace timer fires — mock data should appear
    act(() => {
      vi.advanceTimersByTime(2100);
    });

    expect(screen.getByText('Elena Vogt (CTO)')).toBeInTheDocument();
  });

  it('shows no messages before grace period elapses and no live data', () => {
    renderPanel();

    // Neither live nor mock — within grace window
    expect(screen.queryByText('Elena Vogt (CTO)')).not.toBeInTheDocument();
    expect(screen.queryByText('Sarah Connor')).not.toBeInTheDocument();
  });
});

describe('MailPanel — DraftPreview section', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    capturedMailStateListener = null;
    capturedDraftPreviewListener = null;
    capturedSendDoneListener = null;
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it('shows draft preview section when email_draft_preview arrives', async () => {
    renderPanel();

    act(() => {
      capturedDraftPreviewListener?.({
        draft_id: 'draft-abc',
        to: 'sarah@example.com',
        subject: 'Treffen morgen',
        body_preview: 'Lass uns um 10 Uhr treffen.',
        created_at: new Date().toISOString(),
      });
    });

    expect(screen.getByText('sarah@example.com')).toBeInTheDocument();
    expect(screen.getByText('Treffen morgen')).toBeInTheDocument();
    // Confirmation prompt
    expect(screen.getByText(/JA/)).toBeInTheDocument();
  });

  it('truncates body_preview to 80 chars', async () => {
    renderPanel();

    const longBody = 'A'.repeat(100);
    act(() => {
      capturedDraftPreviewListener?.({
        draft_id: 'draft-long',
        to: 'test@example.com',
        subject: 'Long body',
        body_preview: longBody,
        created_at: new Date().toISOString(),
      });
    });

    // Displayed text must be truncated
    const truncated = `${'A'.repeat(80)}…`;
    expect(screen.getByText(truncated)).toBeInTheDocument();
  });

  it('hides draft preview after email_send_done arrives', async () => {
    renderPanel();

    act(() => {
      capturedDraftPreviewListener?.({
        draft_id: 'draft-abc',
        to: 'sarah@example.com',
        subject: 'Treffen morgen',
        body_preview: 'Lass uns treffen.',
        created_at: new Date().toISOString(),
      });
    });

    expect(screen.getByText('sarah@example.com')).toBeInTheDocument();

    act(() => {
      capturedSendDoneListener?.({
        draft_id: 'draft-abc',
        success: true,
        message_id: 'msg-xyz',
      });
    });

    expect(screen.queryByText('sarah@example.com')).not.toBeInTheDocument();
  });
});

describe('MailPanel — compact mode', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    capturedMailStateListener = null;
    capturedDraftPreviewListener = null;
    capturedSendDoneListener = null;
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it('renders live unread count in compact mode', async () => {
    renderPanel('compact');

    act(() => {
      capturedMailStateListener?.({
        messages: liveMessages,
        unread_count: 3,
      });
    });

    expect(screen.getByText('3')).toBeInTheDocument();
  });

  it('shows draft preview in compact mode', async () => {
    renderPanel('compact');

    act(() => {
      capturedDraftPreviewListener?.({
        draft_id: 'd1',
        to: 'boss@corp.com',
        subject: 'Status report',
        body_preview: 'Everything is on track.',
        created_at: new Date().toISOString(),
      });
    });

    expect(screen.getByText('boss@corp.com')).toBeInTheDocument();
  });
});
