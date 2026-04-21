/**
 * HudCornerBrackets — four L-shaped corner accent marks.
 *
 * Mounted as an absolute overlay inside a `position: relative` parent.
 * Animates on focused/hover via CSS classes on the parent `.hud-panel`.
 */

import type { ReactElement } from 'react';
import '../hud.css';
import './HudCornerBrackets.css';

export interface HudCornerBracketsProps {
  /** No props required — styling driven by parent .hud-panel state classes. */
  className?: string;
}

export function HudCornerBrackets({ className }: HudCornerBracketsProps): ReactElement {
  return (
    <div
      className={['hud-corner-brackets', className].filter(Boolean).join(' ')}
      aria-hidden
    >
      <span className="hud-corner-bracket tl" />
      <span className="hud-corner-bracket tr" />
      <span className="hud-corner-bracket bl" />
      <span className="hud-corner-bracket br" />
    </div>
  );
}

export default HudCornerBrackets;
