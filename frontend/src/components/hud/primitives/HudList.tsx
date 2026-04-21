/**
 * HudList / HudListItem — styled list primitives for panel content.
 *
 * API is minimal for Batch 1; panels consuming these in Batch 3+ will extend
 * via composition rather than added props.
 */

import type { ReactElement, ReactNode } from 'react';
import '../hud.css';

export interface HudListProps {
  children: ReactNode;
  className?: string;
}

export interface HudListItemProps {
  children: ReactNode;
  className?: string;
}

/** Styled `<ul>` wrapper. Children should be `<HudListItem>` elements. */
export function HudList({ children, className }: HudListProps): ReactElement {
  return (
    <ul className={['hud-list', className].filter(Boolean).join(' ')}>
      {children}
    </ul>
  );
}

/** Styled `<li>` item. Provide a stable `key` on the call-site. */
export function HudListItem({
  children,
  className,
}: HudListItemProps): ReactElement {
  return (
    <li className={['hud-list-item', className].filter(Boolean).join(' ')}>
      {children}
    </li>
  );
}

export default HudList;
