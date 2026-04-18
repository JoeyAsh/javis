import { useEffect, useRef, useState, type ReactElement } from 'react';
import { mailMock } from '../../mock/mailMock';
import {
  subscribeEmailDraftPreviewStream,
  subscribeEmailSendDoneStream,
  subscribeMailStateStream,
} from '../../hooks/useWebSocket';
import type { EmailDraftPreviewPayload, MailMessage, PanelMode } from '../../types';

// ============ Sub-components ============

export interface DraftPreviewProps {
  draft: EmailDraftPreviewPayload;
}

export function DraftPreview({ draft }: DraftPreviewProps): ReactElement {
  const preview =
    draft.body_preview.length > 80
      ? `${draft.body_preview.slice(0, 80)}…`
      : draft.body_preview;

  return (
    <div
      style={{
        border: '1px solid var(--accent)',
        padding: '8px 10px',
        marginBottom: 8,
        background: 'rgba(76,168,232,0.06)',
      }}
    >
      <div
        style={{
          fontSize: 9,
          color: 'var(--accent-bright)',
          letterSpacing: 1.5,
          marginBottom: 6,
          fontWeight: 600,
        }}
      >
        SENDEN — SAG &apos;JA&apos; ZUM BESTÄTIGEN
      </div>
      <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 2 }}>
        <span style={{ color: 'var(--text-muted)' }}>AN: </span>
        {draft.to}
      </div>
      <div style={{ fontSize: 11, color: 'var(--text)', marginBottom: 4 }}>
        <span style={{ color: 'var(--text-muted)' }}>BETREFF: </span>
        {draft.subject}
      </div>
      <div
        style={{
          fontSize: 10,
          color: 'var(--text-muted)',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
      >
        {preview}
      </div>
    </div>
  );
}

// ============ Layout sub-views ============

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h`;
  return `${Math.floor(hrs / 24)}d`;
}

interface MailCompactProps {
  messages: MailMessage[];
  unreadCount: number;
  draft: EmailDraftPreviewPayload | null;
}

function MailCompact({ messages, unreadCount, draft }: MailCompactProps): ReactElement {
  const vip = messages.filter((m) => m.isVip).length;
  const latest = messages[0];
  return (
    <>
      {draft && <DraftPreview draft={draft} />}
      <div className="window-compact-row">
        <span style={{ color: 'var(--accent-bright)', fontWeight: 500 }}>{unreadCount}</span>
        <span className="mono-small">ungelesen</span>
        <span style={{ color: 'var(--text-muted)' }}>·</span>
        <span style={{ color: 'var(--accent-speak)', fontWeight: 500 }}>{vip}</span>
        <span className="mono-small">VIP</span>
      </div>
      {latest && (
        <div
          className="window-compact-row truncate"
          style={{ fontSize: 11, color: 'var(--text-muted)' }}
        >
          {latest.sender}
        </div>
      )}
    </>
  );
}

interface MailExpandedProps {
  messages: MailMessage[];
  unreadCount: number;
  draft: EmailDraftPreviewPayload | null;
}

function MailExpanded({ messages, unreadCount, draft }: MailExpandedProps): ReactElement {
  return (
    <>
      {draft && <DraftPreview draft={draft} />}
      <div
        style={{
          display: 'flex',
          alignItems: 'baseline',
          gap: 6,
          marginBottom: 8,
          padding: '0 2px',
        }}
      >
        <span style={{ color: 'var(--accent-bright)', fontWeight: 600, fontSize: 18 }}>
          {unreadCount}
        </span>
        <span style={{ fontSize: 10, color: 'var(--text-muted)', letterSpacing: 1 }}>
          UNGELESEN
        </span>
      </div>
      {messages.slice(0, 5).map((msg) => (
        <div className="list-item" key={msg.id}>
          <div
            style={{
              display: 'flex',
              alignItems: 'baseline',
              gap: 6,
              marginBottom: 2,
            }}
          >
            {msg.isVip && (
              <span
                style={{
                  fontSize: 8,
                  color: 'var(--accent-speak)',
                  border: '1px solid var(--accent-bright)',
                  padding: '1px 4px',
                  letterSpacing: 1,
                }}
              >
                VIP
              </span>
            )}
            <span
              style={{
                fontSize: 11,
                color: msg.isVip ? 'var(--accent-bright)' : 'var(--text-secondary)',
                fontWeight: 500,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {msg.sender}
            </span>
            <span className="mono-small" style={{ marginLeft: 'auto', flexShrink: 0 }}>
              {relativeTime(msg.receivedAt)}
            </span>
          </div>
          <div
            style={{
              fontSize: 12,
              color: 'var(--text)',
              marginBottom: 2,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {msg.subject}
          </div>
          <div
            style={{
              fontSize: 10,
              color: 'var(--text-muted)',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {msg.preview}
          </div>
        </div>
      ))}
    </>
  );
}

// ============ Main component ============

export interface MailPanelProps {
  mode?: PanelMode;
}

/** Time window (ms) after connect before falling back to mock data is abandoned. */
const LIVE_GRACE_MS = 2000;

export function MailPanel({ mode = 'expanded' }: MailPanelProps): ReactElement {
  const [messages, setMessages] = useState<MailMessage[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [draft, setDraft] = useState<EmailDraftPreviewPayload | null>(null);
  const [hasLiveData, setHasLiveData] = useState(false);

  // Flash state for send-done confirmation
  const [sendFlash, setSendFlash] = useState(false);
  const flashTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // After LIVE_GRACE_MS with no mail_state message, fall back to mock
  const graceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [gracePassed, setGracePassed] = useState(false);

  useEffect(() => {
    graceRef.current = setTimeout(() => {
      setGracePassed(true);
    }, LIVE_GRACE_MS);

    const unsubMailState = subscribeMailStateStream((payload) => {
      setHasLiveData(true);
      setMessages(payload.messages);
      setUnreadCount(payload.unread_count);
    });

    const unsubDraftPreview = subscribeEmailDraftPreviewStream((payload) => {
      setDraft(payload);
    });

    const unsubSendDone = subscribeEmailSendDoneStream((payload) => {
      setDraft(null);
      if (payload.success) {
        setSendFlash(true);
        if (flashTimerRef.current) clearTimeout(flashTimerRef.current);
        flashTimerRef.current = setTimeout(() => setSendFlash(false), 1500);
        // Decrement the local count optimistically
        setUnreadCount((prev) => Math.max(0, prev - 1));
      }
    });

    return () => {
      if (graceRef.current) clearTimeout(graceRef.current);
      if (flashTimerRef.current) clearTimeout(flashTimerRef.current);
      unsubMailState();
      unsubDraftPreview();
      unsubSendDone();
    };
  }, []);

  // Decide data source: live data wins; otherwise fall back to mock after grace period
  const displayMessages = hasLiveData ? messages : gracePassed ? mailMock : [];
  const displayUnread = hasLiveData
    ? unreadCount
    : gracePassed
      ? mailMock.filter((m) => m.unread).length
      : 0;

  const flashStyle: React.CSSProperties = sendFlash
    ? { outline: '1px solid var(--accent)', transition: 'outline 300ms' }
    : {};

  if (mode === 'compact') {
    return (
      <div style={flashStyle}>
        <MailCompact messages={displayMessages} unreadCount={displayUnread} draft={draft} />
      </div>
    );
  }

  return (
    <div style={flashStyle}>
      <MailExpanded messages={displayMessages} unreadCount={displayUnread} draft={draft} />
    </div>
  );
}

export default MailPanel;
