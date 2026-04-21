/**
 * HudStatusBadge — small pill indicating a status with semantic color.
 */

import type { ReactElement, ReactNode } from 'react';
import './HudStatusBadge.css';

export type BadgeStatus = 'ok' | 'warn' | 'error' | 'info' | 'default';

export interface HudStatusBadgeProps {
  status?: BadgeStatus;
  children: ReactNode;
  className?: string;
}

const STATUS_CLASS: Record<BadgeStatus, string> = {
  ok: 'hud-status-badge--ok',
  warn: 'hud-status-badge--warn',
  error: 'hud-status-badge--error',
  info: 'hud-status-badge--info',
  default: '',
};

export function HudStatusBadge({
  status = 'default',
  children,
  className,
}: HudStatusBadgeProps): ReactElement {
  return (
    <span
      className={['hud-status-badge', STATUS_CLASS[status], className]
        .filter(Boolean)
        .join(' ')}
    >
      {children}
    </span>
  );
}

export default HudStatusBadge;
