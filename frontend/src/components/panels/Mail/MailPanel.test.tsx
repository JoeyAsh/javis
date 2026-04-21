/**
 * MailPanel — Vitest + RTL tests (modular folder rebuild).
 */
import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

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
    return () => { capturedMailStateListener = null; };
  }),
  subscribeEmailDraftPreviewStream: vi.fn((listener: EmailDraftPreviewListener) => {
    capturedDraftPreviewListener = listener;
    return () => { capturedDraftPreviewListener = null; };
  }),
  subscribeEmailSendDoneStream: vi.fn((listener: EmailSendDoneListener) => {
    capturedSendDoneListener = listener;
    return () => { capturedSendDoneListener = null; };
  }),
}));

const mockPlayOneShot = vi.fn();
vi.mock('../../../hud/SfxContext', () => ({
  useSfx: () => ({ playOneShot: mockPlayOneShot }),
}));

import { MailPanel } from './MailPanel';
import type { MailMessage } from '../../../types';

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

describe('MailPanel — live data', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    capturedMailStateListener = null;
    capturedDraftPreviewListener = null;
    capturedSendDoneListener = null;
    mockPlayOneShot.mockClear();
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it('renders unread count and senders from live mail_state', async () => {
    render(<MailPanel mode="expanded" />);
    act(() => {
      capturedMailStateListener?.({ messages: liveMessages, unread_count: 7 });
    });
    // Unread header removed per prototype — only row content shown
    expect(screen.getByText('Sarah Connor')).toBeInTheDocument();
    expect(screen.getByText('John Doe')).toBeInTheDocument();
  });

  it('mock senders absent when live data arrived', async () => {
    render(<MailPanel mode="expanded" />);
    act(() => {
      capturedMailStateListener?.({ messages: liveMessages, unread_count: 2 });
    });
    expect(screen.queryByText('Elena Vogt (CTO)')).not.toBeInTheDocument();
  });

  it('falls back to mock after 2s grace period', () => {
    render(<MailPanel mode="expanded" />);
    act(() => { vi.advanceTimersByTime(2100); });
    expect(screen.getByText('Elena Vogt (CTO)')).toBeInTheDocument();
  });

  it('shows no messages before grace period elapses and no live data', () => {
    render(<MailPanel mode="expanded" />);
    expect(screen.queryByText('Elena Vogt (CTO)')).not.toBeInTheDocument();
    expect(screen.queryByText('Sarah Connor')).not.toBeInTheDocument();
  });

  it('renders correct number of rows for 2 messages', async () => {
    render(<MailPanel mode="expanded" />);
    act(() => {
      capturedMailStateListener?.({ messages: liveMessages, unread_count: 2 });
    });
    const rows = screen.getAllByRole('button');
    expect(rows.length).toBeGreaterThanOrEqual(2);
  });

  it('fires click SFX on row click', () => {
    render(<MailPanel mode="expanded" />);
    act(() => {
      capturedMailStateListener?.({ messages: liveMessages, unread_count: 2 });
    });
    fireEvent.click(screen.getByText('Meeting tomorrow'));
    expect(mockPlayOneShot).toHaveBeenCalledWith('click');
  });
});

describe('MailPanel — DraftPreview', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    capturedMailStateListener = null;
    capturedDraftPreviewListener = null;
    capturedSendDoneListener = null;
    mockPlayOneShot.mockClear();
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it('shows draft preview when email_draft_preview arrives', async () => {
    render(<MailPanel mode="expanded" />);
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
    expect(screen.getByText(/JA/)).toBeInTheDocument();
  });

  it('truncates body_preview to 80 chars', async () => {
    render(<MailPanel mode="expanded" />);
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
    const truncated = `${'A'.repeat(80)}…`;
    expect(screen.getByText(truncated)).toBeInTheDocument();
  });

  it('hides draft preview after email_send_done', async () => {
    render(<MailPanel mode="expanded" />);
    act(() => {
      capturedDraftPreviewListener?.({
        draft_id: 'draft-abc', to: 'sarah@example.com',
        subject: 'Treffen morgen', body_preview: 'Lass uns treffen.',
        created_at: new Date().toISOString(),
      });
    });
    expect(screen.getByText('sarah@example.com')).toBeInTheDocument();
    act(() => {
      capturedSendDoneListener?.({
        draft_id: 'draft-abc', success: true, message_id: 'msg-xyz',
      });
    });
    expect(screen.queryByText('sarah@example.com')).not.toBeInTheDocument();
  });
});

describe('MailPanel — compact mode', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    capturedMailStateListener = null;
    mockPlayOneShot.mockClear();
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it('renders live unread count in compact mode', async () => {
    render(<MailPanel mode="compact" />);
    act(() => {
      capturedMailStateListener?.({ messages: liveMessages, unread_count: 3 });
    });
    expect(screen.getByText('3')).toBeInTheDocument();
  });
});
