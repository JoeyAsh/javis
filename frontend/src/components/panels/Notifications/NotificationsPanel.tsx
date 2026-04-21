/**
 * NotificationsPanel — panel body for HUD notifications.
 * Returns only body content; the Window wrapper supplies chrome via HudPanel.
 *
 * Prototype reference: NotificationsPanel() in JARVIS HUD Hypermodern.html
 * Severity-coloured left-border rows with title + relative time + detail.
 *
 * SFX: info_pop on new toast mount, info_dismiss on dismiss,
 *      select on item click (from spec #36/#37/#38).
 */
import { useEffect, useMemo, useRef } from 'react';
import type { ReactElement } from 'react';
import { notificationsMock } from '../../../mock/notificationsMock';
import { useMockTicker } from '../../../mock/useMockTicker';
import { useNotifications } from '../../../hooks/useNotifications';
import type { HudNotification, NotificationSeverity, PanelMode } from '../../../types';
import { NotificationItem } from './NotificationItem';
import './NotificationsPanel.css';

export interface NotificationsPanelProps {
  /** Optional override — short-circuits the live subscription. */
  notifications?: HudNotification[];
  paused?: boolean;
  mode?: PanelMode;
}

function severityDotColor(sev: NotificationSeverity): string {
  switch (sev) {
    case 'urgent':
      return 'var(--error)';
    case 'warning':
      return 'var(--warning)';
    case 'info':
      return 'var(--accent-bright)';
  }
}

function severityTitleColor(sev: NotificationSeverity): string {
  switch (sev) {
    case 'urgent':
      return 'var(--error)';
    case 'warning':
      return 'var(--warning)';
    case 'info':
      return 'var(--accent-bright)';
  }
}

// ---- Compact mode ----

function NotificationsCompact({
  notifications,
}: {
  notifications: HudNotification[];
}): ReactElement {
  const top = notifications[0];
  const remaining = Math.max(0, notifications.length - 1);

  if (!top) {
    return (
      <div className="notif-compact">
        <span className="notif-empty">Keine aktiven Benachrichtigungen</span>
      </div>
    );
  }

  return (
    <div className="notif-compact">
      <div className="notif-compact__row">
        <span
          aria-hidden
          className="notif-compact__dot"
          style={{ background: severityDotColor(top.severity) }}
        />
        <span
          className="notif-compact__title"
          style={{ color: severityTitleColor(top.severity) }}
        >
          {top.title}
        </span>
        {remaining > 0 && (
          <span className="notif-compact__badge">+{remaining}</span>
        )}
      </div>
      <div className="notif-compact__detail">{top.detail}</div>
    </div>
  );
}

// ---- Expanded mode ----

function NotificationsExpanded({
  notifications,
}: {
  notifications: HudNotification[];
}): ReactElement {
  if (notifications.length === 0) {
    return (
      <div className="notif-panel">
        <span className="notif-empty">Keine aktiven Benachrichtigungen</span>
      </div>
    );
  }

  return (
    <div className="notif-panel">
      {notifications.map((n) => (
        <NotificationItem key={n.id} notification={n} />
      ))}
    </div>
  );
}

// ---- Props + main export ----

/**
 * NotificationsPanel body — renders HUD notifications with severity colouring.
 * Accepts optional `notifications` prop for testing; otherwise subscribes to live WS.
 */
export function NotificationsPanel({
  notifications,
  paused = false,
  mode = 'expanded',
}: NotificationsPanelProps): ReactElement {
  const { notifications: live, isLive } = useNotifications();
  const source: HudNotification[] =
    notifications !== undefined ? notifications : isLive ? live : notificationsMock;

  // Track previous IDs to detect new arrivals (for info_pop SFX).
  const prevIdsRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    const currentIds = new Set(source.map((n) => n.id));
    prevIdsRef.current = currentIds;
  });

  // Rotate the mock source for liveliness; keep live notifications stable.
  const tick = useMockTicker(4000, paused || isLive);
  const rotated = useMemo<HudNotification[]>(() => {
    if (isLive || source.length === 0) return source;
    const offset = tick % source.length;
    return [...source.slice(offset), ...source.slice(0, offset)];
  }, [source, tick, isLive]);

  return mode === 'compact' ? (
    <NotificationsCompact notifications={rotated} />
  ) : (
    <NotificationsExpanded notifications={rotated} />
  );
}

export default NotificationsPanel;
