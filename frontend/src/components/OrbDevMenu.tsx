import type { ReactElement } from 'react';
import type { AppOrbState } from '../types';
import { useSettings } from '../hooks/useSettings';
import type { OrbVariant } from '../hooks/useSettings';

export interface OrbDevMenuProps {
  /** Current override — null means "live" (follow real pipeline). */
  override: AppOrbState | null;
  /** Called with new override state, or null to return to live mode. */
  onSet: (override: AppOrbState | null) => void;
  /**
   * Optional STOP handler. When supplied, renders an extra button that
   * aborts any in-flight voice turn on the backend. Hidden when omitted.
   */
  onStop?: () => void;
}

interface StateOption {
  key: AppOrbState | 'live';
  label: string;
  title: string;
}

const OPTIONS: ReadonlyArray<StateOption> = [
  { key: 'idle', label: 'IDLE', title: 'Force orb to idle state' },
  { key: 'listening', label: 'LISTEN', title: 'Force orb to listening state' },
  { key: 'thinking', label: 'THINK', title: 'Force orb to thinking state' },
  { key: 'speaking', label: 'SPEAK', title: 'Force orb to speaking state' },
  { key: 'working', label: 'WORK', title: 'Force orb to working state (tool execution)' },
  { key: 'live', label: 'LIVE', title: 'Follow real pipeline state' },
];

const VARIANT_OPTIONS: ReadonlyArray<{ key: OrbVariant; label: string }> = [
  { key: 'classic', label: 'ORB1' },
  { key: 'hypermodern', label: 'ORB2' },
];

export function OrbDevMenu({
  override,
  onSet,
  onStop,
}: OrbDevMenuProps): ReactElement {
  const active: AppOrbState | 'live' = override ?? 'live';
  const { settings, setOrbVariant } = useSettings();
  const variant = settings.orbVariant;

  return (
    <div
      className="orb-devmenu"
      role="group"
      aria-label="Orb dev menu"
    >
      {/* Variant switcher row */}
      <span className="orb-devmenu__label">VARIANT</span>
      {VARIANT_OPTIONS.map((opt) => (
        <button
          key={opt.key}
          type="button"
          className={`orb-devmenu__btn ${
            variant === opt.key ? 'orb-devmenu__btn--active' : ''
          }`.trim()}
          onClick={() => { setOrbVariant(opt.key); }}
          aria-pressed={variant === opt.key}
          title={`Switch to ${opt.key} orb`}
        >
          {opt.label}
        </button>
      ))}

      {/* Visual separator */}
      <span className="orb-devmenu__sep" aria-hidden="true" />

      {/* State-override row */}
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
            onClick={() => { onSet(opt.key === 'live' ? null : opt.key); }}
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
