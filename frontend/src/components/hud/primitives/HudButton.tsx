/**
 * HudButton — styled button primitive with baked-in SFX feedback.
 *
 * Plays `click` on every click. Plays `hover` on mouseenter (debounced 200 ms
 * per instance via a `useRef` timer). Both sounds are no-ops when `disabled`.
 *
 * SFX are sourced from the nearest `SfxProvider` via `useSfx()`.
 */

import { useCallback, useRef } from 'react';
import type { MouseEvent as ReactMouseEvent, ReactElement, ReactNode } from 'react';
import { useSfx } from '../../../hud/SfxContext';
import '../hud.css';

export type HudButtonVariant = 'default' | 'ghost' | 'primary';

export interface HudButtonProps {
  onClick?: (e: ReactMouseEvent<HTMLButtonElement>) => void;
  disabled?: boolean;
  variant?: HudButtonVariant;
  children: ReactNode;
  className?: string;
  'aria-label'?: string;
  type?: 'button' | 'submit' | 'reset';
}

const HOVER_DEBOUNCE_MS = 200;

/**
 * Reusable HUD button with JARVIS design-system styling and automatic SFX.
 */
export function HudButton({
  onClick,
  disabled = false,
  variant = 'default',
  children,
  className,
  'aria-label': ariaLabel,
  type = 'button',
}: HudButtonProps): ReactElement {
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
    // Debounce: clear any previous pending hover sound.
    if (hoverTimerRef.current !== null) {
      clearTimeout(hoverTimerRef.current);
    }
    hoverTimerRef.current = setTimeout(() => {
      hoverTimerRef.current = null;
      playOneShot('hover');
    }, HOVER_DEBOUNCE_MS);
  }, [disabled, playOneShot]);

  const handleMouseLeave = useCallback(() => {
    // Cancel pending hover sound if the mouse left before debounce fires.
    if (hoverTimerRef.current !== null) {
      clearTimeout(hoverTimerRef.current);
      hoverTimerRef.current = null;
    }
  }, []);

  const variantClass =
    variant === 'ghost'
      ? 'hud-btn--ghost'
      : variant === 'primary'
        ? 'hud-btn--primary'
        : '';

  return (
    <button
      type={type}
      disabled={disabled}
      aria-label={ariaLabel}
      className={['hud-btn', variantClass, className].filter(Boolean).join(' ')}
      onClick={handleClick}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      {children}
    </button>
  );
}

export default HudButton;
