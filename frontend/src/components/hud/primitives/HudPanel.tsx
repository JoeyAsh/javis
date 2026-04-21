/**
 * HudPanel — master shell for JARVIS HUD panels.
 *
 * Composes HudCornerBrackets, HudLightTrace, and HudBloom internally.
 * Content is rendered above all decoration layers via a positioned inner
 * container.
 *
 * @example
 * ```tsx
 * <HudPanel focused icon={<IconNode />} title="TITLE" badge={<HudStatusBadge>LIVE</HudStatusBadge>}>
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
  /**
   * Icon node rendered in the header's `.ix` span (accent-bright color).
   * Mutually exclusive with the legacy `header` prop — prefer `icon` + `title`.
   */
  icon?: ReactNode;
  /**
   * Title string rendered in the header's `.tt` span (text-secondary color).
   */
  title?: ReactNode;
  /**
   * @deprecated Pass `icon` and `title` separately instead.
   * Legacy catch-all header node — rendered as-is inside the header row when
   * `icon` and `title` are both undefined.
   */
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
  icon,
  title,
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

  // Determine whether a header row should render.
  const hasHeader =
    icon !== undefined ||
    title !== undefined ||
    header !== undefined ||
    badge !== undefined;

  return (
    <div className={panelClass} style={style}>
      {/* Decoration layers — below content */}
      <HudBloom />
      <HudLightTrace />
      <HudCornerBrackets />

      {/* Header row */}
      {hasHeader && (
        <div
          ref={headerRef}
          onClick={onHeaderClick}
          className="hud-panel__header"
          style={{
            position: 'relative',
            zIndex: 2,
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '0 10px',
            height: 26,
            minHeight: 26,
            borderBottom: '1px solid var(--border)',
            background: 'rgba(76,168,232,.04)',
            userSelect: 'none',
            cursor: 'grab',
            fontSize: 9,
            letterSpacing: 2,
            textTransform: 'uppercase' as const,
            fontFamily: 'var(--font)',
          }}
        >
          {/* Icon in accent-bright .ix span, title in text-secondary .tt span */}
          {(icon !== undefined || title !== undefined) ? (
            <div style={{ flex: 1, minWidth: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
              {icon !== undefined && <span className="ix">{icon}</span>}
              {title !== undefined && <span className="tt" style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{title}</span>}
            </div>
          ) : header !== undefined ? (
            <div style={{ flex: 1, minWidth: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
              {header}
            </div>
          ) : null}
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
