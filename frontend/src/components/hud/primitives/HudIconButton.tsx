/**
 * HudIconButton — icon-only variant of HudButton.
 *
 * Same SFX baking as HudButton (click + hover debounced 200 ms).
 * Accepts any ReactNode as icon child. No text label — use `aria-label`.
 */

import { useCallback, useRef } from 'react';
import type { MouseEvent as ReactMouseEvent, ReactElement, ReactNode } from 'react';
import { useSfx } from '../../../hud/SfxContext';
import '../hud.css';
import './HudIconButton.css';

export interface HudIconButtonProps {
  onClick?: (e: ReactMouseEvent<HTMLButtonElement>) => void;
  disabled?: boolean;
  /** Visual active state (e.g. pin toggled on). */
  active?: boolean;
  children: ReactNode;
  className?: string;
  'aria-label': string;
  type?: 'button' | 'submit' | 'reset';
}

const HOVER_DEBOUNCE_MS = 200;

/**
 * Icon-only HUD button with JARVIS styling and automatic SFX.
 */
export function HudIconButton({
  onClick,
  disabled = false,
  active = false,
  children,
  className,
  'aria-label': ariaLabel,
  type = 'button',
}: HudIconButtonProps): ReactElement {
  const { playOneShot } = useSfx();
  const hoverTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleClick = useCallback(
    (e: ReactMouseEvent<HTMLButtonElement>) => {
      if (disabled) return;
      playOneShot('click');
      onClick?.(e);
    },
    [disabled, onClick, playOneShot],
  );

  const handleMouseEnter = useCallback(() => {
    if (disabled) return;
    if (hoverTimerRef.current !== null) {
      clearTimeout(hoverTimerRef.current);
    }
    hoverTimerRef.current = setTimeout(() => {
      hoverTimerRef.current = null;
      playOneShot('hover');
    }, HOVER_DEBOUNCE_MS);
  }, [disabled, playOneShot]);

  const handleMouseLeave = useCallback(() => {
    if (hoverTimerRef.current !== null) {
      clearTimeout(hoverTimerRef.current);
      hoverTimerRef.current = null;
    }
  }, []);

  return (
    <button
      type={type}
      disabled={disabled}
      aria-label={ariaLabel}
      aria-pressed={active}
      className={[
        'hud-icon-btn',
        active ? 'hud-icon-btn--active' : '',
        className,
      ]
        .filter(Boolean)
        .join(' ')}
      onClick={handleClick}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      {children}
    </button>
  );
}

export default HudIconButton;
