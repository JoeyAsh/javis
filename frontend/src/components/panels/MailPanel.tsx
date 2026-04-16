import type { ReactElement } from 'react';
import { mailMock } from '../../mock/mailMock';
import type { MailMessage, PanelMode } from '../../types';

export interface MailPanelProps {
  messages?: MailMessage[];
  mode?: PanelMode;
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h`;
  return `${Math.floor(hrs / 24)}d`;
}

function MailCompact({ messages }: { messages: MailMessage[] }): ReactElement {
  const unread = messages.filter((m) => m.unread).length;
  const vip = messages.filter((m) => m.isVip).length;
  const latest = messages[0];
  return (
    <>
      <div className="window-compact-row">
        <span style={{ color: 'var(--accent-bright)', fontWeight: 500 }}>{unread}</span>
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

function MailExpanded({ messages }: { messages: MailMessage[] }): ReactElement {
  return (
    <>
      {messages.map((msg) => (
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

export function MailPanel({
  messages = mailMock,
  mode = 'expanded',
}: MailPanelProps): ReactElement {
  return mode === 'compact' ? (
    <MailCompact messages={messages} />
  ) : (
    <MailExpanded messages={messages} />
  );
}

export default MailPanel;
