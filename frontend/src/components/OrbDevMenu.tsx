import type { ReactElement } from 'react';
import type { OrbState } from '../types';

export interface OrbDevMenuProps {
  /** Current override — null means "live" (follow real pipeline). */
  override: OrbState | null;
  /** Called with new override state, or null to return to live mode. */
  onSet: (override: OrbState | null) => void;
  /**
   * Optional STOP handler. When supplied, renders an extra button that
   * aborts any in-flight voice turn on the backend. Hidden when omitted.
   */
  onStop?: () => void;
}

interface StateOption {
  key: OrbState | 'live';
  label: string;
  title: string;
}

const OPTIONS: ReadonlyArray<StateOption> = [
  { key: 'idle', label: 'IDLE', title: 'Force orb to idle state' },
  { key: 'listening', label: 'LISTEN', title: 'Force orb to listening state' },
  { key: 'thinking', label: 'THINK', title: 'Force orb to thinking state' },
  { key: 'speaking', label: 'SPEAK', title: 'Force orb to speaking state' },
  { key: 'live', label: 'LIVE', title: 'Follow real pipeline state' },
];

export function OrbDevMenu({
  override,
  onSet,
  onStop,
}: OrbDevMenuProps): ReactElement {
  const active: OrbState | 'live' = override ?? 'live';
  return (
    <div
      className="orb-devmenu"
      role="group"
      aria-label="Orb state override (dev)"
    >
      <span className="orb-devmenu__label">ORB</span>
      {OPTIONS.map((opt) => {
        const isActive = opt.key === active;
        return (
          <button
            key={opt.key}
            type="button"
            className={`orb-devmenu__btn ${
              isActive ? 'orb-devmenu__btn--active' : ''
            }`.trim()}
            onClick={() => onSet(opt.key === 'live' ? null : opt.key)}
            aria-pressed={isActive}
            title={opt.title}
          >
            {opt.label}
          </button>
        );
      })}
      {onStop ? (
        <button
          key="stop"
          type="button"
          className="orb-devmenu__btn orb-devmenu__btn--stop"
          onClick={onStop}
          title="Abort the in-flight voice turn"
          aria-label="Stop current voice turn"
        >
          STOP
        </button>
      ) : null}
    </div>
  );
}

export default OrbDevMenu;
