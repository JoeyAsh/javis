/**
 * HudPanel — master shell for JARVIS HUD panels.
 *
 * Composes HudCornerBrackets, HudLightTrace, and HudBloom internally.
 * Content is rendered above all decoration layers via a positioned inner
 * container.
 *
 * @example
 * ```tsx
 * <HudPanel focused header={<span>Title</span>} badge={<HudStatusBadge>LIVE</HudStatusBadge>}>
 *   <p>Panel body</p>
 * </HudPanel>
 * ```
 */

import type React from 'react';
import type { ReactElement, ReactNode } from 'react';
import { HudCornerBrackets } from './HudCornerBrackets';
import { HudLightTrace } from './HudLightTrace';
import { HudBloom } from './HudBloom';
import '../hud.css';

export type HudPanelVariant = 'default' | 'dev';

export interface HudPanelProps {
  /** Whether this panel is the currently focused window. */
  focused?: boolean;
  /** Visual variant — 'dev' uses warning border color. */
  variant?: HudPanelVariant;
  /** Optional header node rendered inside the panel chrome. */
  header?: ReactNode;
  /** Optional badge placed at the end of the header row. */
  badge?: ReactNode;
  /**
   * Ref forwarded to the internal header wrapper element.
   * Used by Window to attach drag/swap-drag listeners to the header row.
   */
  headerRef?: React.RefCallback<HTMLDivElement>;
  /** Click handler for the header row (used for double-click maximize in Window). */
  onHeaderClick?: React.MouseEventHandler<HTMLDivElement>;
  className?: string;
  /** Optional inline style — use sparingly; prefer CSS variables and classes. */
  style?: React.CSSProperties;
  children?: ReactNode;
}

/**
 * Master shell panel for the JARVIS HUD.
 * Glass background + hairline border + corner brackets + light traces + bloom.
 */
export function HudPanel({
  focused = false,
  variant = 'default',
  header,
  badge,
  headerRef,
  onHeaderClick,
  className,
  style,
  children,
}: HudPanelProps): ReactElement {
  const panelClass = [
    'hud-panel',
    focused ? 'hud-panel--focused' : '',
    variant === 'dev' ? 'hud-panel--dev' : '',
    className,
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div className={panelClass} style={style}>
      {/* Decoration layers — below content */}
      <HudBloom />
      <HudLightTrace />
      <HudCornerBrackets />

      {/* Header row */}
      {(header !== undefined || badge !== undefined) && (
        <div
          ref={headerRef}
          onClick={onHeaderClick}
          style={{
            position: 'relative',
            zIndex: 2,
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '0 8px 0 10px',
            height: 30,
            minHeight: 30,
            borderBottom: '1px solid var(--border)',
            background: 'rgba(0,0,0,0.15)',
            userSelect: 'none',
            cursor: 'grab',
          }}
        >
          {header !== undefined && (
            <div style={{ flex: 1, minWidth: 0, display: 'flex', alignItems: 'center', gap: 6 }}>
              {header}
            </div>
          )}
          {badge !== undefined && <div style={{ flexShrink: 0 }}>{badge}</div>}
        </div>
      )}

      {/* Content — above decoration */}
      {children !== undefined && (
        <div style={{ position: 'relative', zIndex: 2 }}>{children}</div>
      )}
    </div>
  );
}

export default HudPanel;
