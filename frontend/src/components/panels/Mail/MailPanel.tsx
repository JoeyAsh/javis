/**
 * MailPanel — panel body for mail messages.
 * Returns only body content; the Window wrapper supplies chrome via HudPanel.
 *
 * Prototype reference: MailPanel() in JARVIS HUD Hypermodern.html
 */
import { useEffect, useRef, useState } from 'react';
import type { ReactElement } from 'react';
import { mailMock } from '../../../mock/mailMock';
import {
  subscribeEmailDraftPreviewStream,
  subscribeEmailSendDoneStream,
  subscribeMailStateStream,
} from '../../../hooks/useWebSocket';
import type { EmailDraftPreviewPayload, MailMessage, PanelMode } from '../../../types';
import { MailItemRow } from './MailItemRow';
import './MailPanel.css';

// ---- Draft preview banner ----

export interface DraftPreviewProps {
  draft: EmailDraftPreviewPayload;
}

export function DraftPreview({ draft }: DraftPreviewProps): ReactElement {
  const preview =
    draft.body_preview.length > 80
      ? `${draft.body_preview.slice(0, 80)}…`
      : draft.body_preview;

  return (
    <div className="mail-draft-preview">
      <div className="mail-draft-preview__label">SENDEN — SAG &apos;JA&apos; ZUM BESTÄTIGEN</div>
      <div className="mail-draft-preview__to">
        <span className="mail-draft-preview__field-label">AN: </span>
        {draft.to}
      </div>
      <div className="mail-draft-preview__subject">
        <span className="mail-draft-preview__field-label">BETREFF: </span>
        {draft.subject}
      </div>
      <div className="mail-draft-preview__body">{preview}</div>
    </div>
  );
}

// ---- Compact mode ----

interface MailCompactProps {
  messages: MailMessage[];
  unreadCount: number;
  draft: EmailDraftPreviewPayload | null;
}

function MailCompact({ messages, unreadCount, draft }: MailCompactProps): ReactElement {
  const vip = messages.filter((m) => m.isVip).length;
  const latest = messages[0];
  return (
    <div className="mail-compact">
      {draft && <DraftPreview draft={draft} />}
      <div className="mail-compact__stats">
        <span>
          <span className="mail-compact__count">{unreadCount}</span>
          {' '}
          <span className="mono-small">ungelesen</span>
        </span>
        <span style={{ color: 'var(--text-muted)' }}>·</span>
        <span>
          <span className="mail-compact__vip">{vip}</span>
          {' '}
          <span className="mono-small">VIP</span>
        </span>
      </div>
      {latest && (
        <div className="mail-compact__sender">{latest.sender}</div>
      )}
    </div>
  );
}

// ---- Expanded mode ----

interface MailExpandedProps {
  messages: MailMessage[];
  unreadCount: number;
  draft: EmailDraftPreviewPayload | null;
}

function MailExpanded({ messages, unreadCount, draft }: MailExpandedProps): ReactElement {
  return (
    <div className="mail-panel">
      {draft && <DraftPreview draft={draft} />}
      <div className="mail-unread-header">
        <span className="mail-unread-header__count">{unreadCount}</span>
        <span className="mail-unread-header__label">UNGELESEN</span>
      </div>
      {messages.slice(0, 5).map((msg) => (
        <MailItemRow key={msg.id} message={msg} />
      ))}
    </div>
  );
}

// ---- Props + main export ----

export interface MailPanelProps {
  mode?: PanelMode;
}

const LIVE_GRACE_MS = 2000;

/**
 * MailPanel body — mail messages with optional draft preview.
 */
export function MailPanel({ mode = 'expanded' }: MailPanelProps): ReactElement {
  const [messages, setMessages] = useState<MailMessage[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [draft, setDraft] = useState<EmailDraftPreviewPayload | null>(null);
  const [hasLiveData, setHasLiveData] = useState(false);
  const [sendFlash, setSendFlash] = useState(false);
  const flashTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const graceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [gracePassed, setGracePassed] = useState(false);

  useEffect(() => {
    graceRef.current = setTimeout(() => setGracePassed(true), LIVE_GRACE_MS);

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

  const displayMessages = hasLiveData ? messages : gracePassed ? mailMock : [];
  const displayUnread = hasLiveData
    ? unreadCount
    : gracePassed
      ? mailMock.filter((m) => m.unread).length
      : 0;

  const flashStyle = sendFlash
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
