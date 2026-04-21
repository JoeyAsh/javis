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
import { useEffect, useMemo, useRef, useState } from 'react';
import type { ReactElement } from 'react';
import { useNotifications } from '../../../hooks/useNotifications';
import type { HudNotification, NotificationSeverity, PanelMode } from '../../../types';
import { usePanelAvailable } from '../../hud/PanelAvailability';
import { NotificationItem } from './NotificationItem';
import './NotificationsPanel.css';

const AVAILABILITY_TIMEOUT_MS = 10_000;

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
 * Returns null if no backend payload arrives within AVAILABILITY_TIMEOUT_MS.
 */
export function NotificationsPanel({
  notifications,
  mode = 'expanded',
}: NotificationsPanelProps): ReactElement | null {
  const { notifications: live, isLive } = useNotifications();
  const [backendAvailable, setBackendAvailable] = useState(true);
  const availabilityTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  usePanelAvailable('notifications', backendAvailable || isLive);

  useEffect(() => {
    if (notifications !== undefined) return;
    availabilityTimerRef.current = setTimeout(() => {
      setBackendAvailable(false);
    }, AVAILABILITY_TIMEOUT_MS);
    return () => {
      if (availabilityTimerRef.current) clearTimeout(availabilityTimerRef.current);
    };
  }, [notifications]);

  // Once live data arrives, cancel the availability timer.
  useEffect(() => {
    if (isLive && availabilityTimerRef.current) {
      clearTimeout(availabilityTimerRef.current);
      setBackendAvailable(true);
    }
  }, [isLive]);

  // Track previous IDs to detect new arrivals (for info_pop SFX).
  const prevIdsRef = useRef<Set<string>>(new Set());
  const source: HudNotification[] = notifications !== undefined ? notifications : live;

  useEffect(() => {
    const currentIds = new Set(source.map((n) => n.id));
    prevIdsRef.current = currentIds;
  });

  const displayed = useMemo<HudNotification[]>(() => source, [source]);

  // Backend not available — hide the panel.
  if (notifications === undefined && !backendAvailable && !isLive) return null;

  return mode === 'compact' ? (
    <NotificationsCompact notifications={displayed} />
  ) : (
    <NotificationsExpanded notifications={displayed} />
  );
}

export default NotificationsPanel;
