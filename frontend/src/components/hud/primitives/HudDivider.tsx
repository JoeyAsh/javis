/**
 * HudDivider — hairline separator (1 px, `--border` color).
 *
 * Orientation: horizontal (default) or vertical.
 */

import type { ReactElement } from 'react';
import '../hud.css';

export interface HudDividerProps {
  orientation?: 'horizontal' | 'vertical';
  className?: string;
}

export function HudDivider({
  orientation = 'horizontal',
  className,
}: HudDividerProps): ReactElement {
  const cls = [
    'hud-divider',
    orientation === 'vertical' ? 'hud-divider--vertical' : '',
    className,
  ]
    .filter(Boolean)
    .join(' ');

  return <hr className={cls} aria-hidden />;
}

export default HudDivider;
