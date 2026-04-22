import type { ReactElement, ReactNode } from 'react';
import { HudInfoBar } from './HudInfoBar';

export interface HudTopBarProps {
  idle: boolean;
  onToggleIdle: () => void;
  onResetLayout: () => void;
  onOpenSettings: () => void;
}

interface IconBtnProps {
  onClick: () => void;
  title: string;
  active?: boolean;
  children: ReactNode;
}

function IconBtn({ onClick, title, active = false, children }: IconBtnProps): ReactElement {
  return (
    <button
      type="button"
      title={title}
      aria-label={title}
      onClick={onClick}
      className={`hud-iconbtn${active ? ' active' : ''}`}
    >
      {children}
    </button>
  );
}

export function HudTopBar({
  idle,
  onToggleIdle,
  onResetLayout,
  onOpenSettings,
}: HudTopBarProps): ReactElement {
  return (
    <div className="hud-topbar">
      <div className="hud-topbar__left">
        <HudInfoBar />
      </div>
      <div className="hud-topbar__right">
        <IconBtn title="Reset layout" onClick={onResetLayout}>
          <svg
            width="12"
            height="12"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <path d="M3 12a9 9 0 1 0 3-6.7" />
            <path d="M3 4v5h5" />
          </svg>
        </IconBtn>
        <IconBtn title="Settings" onClick={onOpenSettings}>
          <svg
            width="12"
            height="12"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <circle cx="12" cy="12" r="3" />
            <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.6-1.1 1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.9.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" />
          </svg>
        </IconBtn>
        <IconBtn title="Idle mode (Ctrl+.)" onClick={onToggleIdle} active={idle}>
          <span style={{ fontSize: 9, letterSpacing: 1 }}>{idle ? 'IDLE' : 'LIVE'}</span>
        </IconBtn>
      </div>
    </div>
  );
}

export default HudTopBar;
