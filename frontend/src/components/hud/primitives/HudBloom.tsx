/**
 * HudBloom — radial gradient overlay with screen mix-blend-mode.
 *
 * `panelBloom` animates idle → hover → focused, driven by parent
 * `.hud-panel` state classes.
 */

import type { ReactElement } from 'react';
import '../hud.css';
import './HudBloom.css';

export interface HudBloomProps {
  className?: string;
}

export function HudBloom({ className }: HudBloomProps): ReactElement {
  return (
    <div
      className={['hud-bloom', className].filter(Boolean).join(' ')}
      aria-hidden
    />
  );
}

export default HudBloom;
