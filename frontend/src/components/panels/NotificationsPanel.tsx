import { useMemo } from 'react';
import type { ReactElement } from 'react';
import { notificationsMock } from '../../mock/notificationsMock';
import { useMockTicker } from '../../mock/useMockTicker';
import type { HudNotification, NotificationSeverity, PanelMode } from '../../types';

export interface NotificationsPanelProps {
  notifications?: HudNotification[];
  paused?: boolean;
  mode?: PanelMode;
}

function severityColor(sev: NotificationSeverity): string {
  switch (sev) {
    case 'urgent':
      return 'var(--danger)';
    case 'warning':
      return 'var(--warning)';
    case 'info':
      return 'var(--accent-bright)';
  }
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const secs = Math.floor(diff / 1000);
  if (secs < 60) return `${secs}s`;
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h`;
  return `${Math.floor(hrs / 24)}d`;
}

function NotificationsCompact({
  notifications,
}: {
  notifications: HudNotification[];
}): ReactElement {
  const top = notifications[0];
  const remaining = Math.max(0, notifications.length - 1);
  if (!top) {
    return (
      <div className="window-compact-row" style={{ color: 'var(--text-muted)' }}>
        Keine aktiven Benachrichtigungen
      </div>
    );
  }
  return (
    <>
      <div className="window-compact-row" style={{ gap: 6 }}>
        <span
          aria-hidden
          style={{
            display: 'inline-block',
            width: 6,
            height: 6,
            background: severityColor(top.severity),
            borderRadius: '50%',
            flexShrink: 0,
          }}
        />
        <span
          className="truncate"
          style={{
            fontSize: 12,
            color: severityColor(top.severity),
            fontWeight: 500,
            flex: 1,
          }}
        >
          {top.title}
        </span>
        {remaining > 0 && (
          <span
            className="mono-small"
            style={{
              color: 'var(--accent-bright)',
              border: '1px solid var(--border)',
              padding: '0 4px',
              borderRadius: 2,
              flexShrink: 0,
            }}
          >
            +{remaining}
          </span>
        )}
      </div>
      <div
        className="window-compact-row truncate"
        style={{ fontSize: 10, color: 'var(--text-muted)' }}
      >
        {top.detail}
      </div>
    </>
  );
}

function NotificationsExpanded({
  notifications,
}: {
  notifications: HudNotification[];
}): ReactElement {
  return (
    <>
      {notifications.map((n) => (
        <div
          className="list-item"
          key={n.id}
          style={{
            borderLeft: `2px solid ${severityColor(n.severity)}`,
            paddingLeft: 8,
            marginBottom: 4,
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'baseline',
              justifyContent: 'space-between',
              gap: 6,
              marginBottom: 2,
            }}
          >
            <span
              style={{
                fontSize: 12,
                color: severityColor(n.severity),
                fontWeight: 500,
              }}
            >
              {n.title}
            </span>
            <span className="mono-small" style={{ flexShrink: 0 }}>
              {relativeTime(n.timestamp)}
            </span>
          </div>
          <div style={{ fontSize: 10, color: 'var(--text-secondary)', lineHeight: 1.4 }}>
            {n.detail}
          </div>
        </div>
      ))}
    </>
  );
}

export function NotificationsPanel({
  notifications = notificationsMock,
  paused = false,
  mode = 'expanded',
}: NotificationsPanelProps): ReactElement {
  const tick = useMockTicker(4000, paused);

  const rotated = useMemo<HudNotification[]>(() => {
    if (notifications.length === 0) return notifications;
    const offset = tick % notifications.length;
    return [...notifications.slice(offset), ...notifications.slice(0, offset)];
  }, [notifications, tick]);

  return mode === 'compact' ? (
    <NotificationsCompact notifications={rotated} />
  ) : (
    <NotificationsExpanded notifications={rotated} />
  );
}

export default NotificationsPanel;
