/**
 * HudPanel — master shell for JARVIS HUD panels.
 *
 * Structure mirrors the prototype Panel component 1:1:
 *   corner brackets (ck tl/tr/bl/br)
 *   side rails (rail l/r)
 *   light trace (trace > i.l + i.r)
 *   header (hdr > ix, tt, dots, badge, hdr-actions)
 *   body
 *
 * Bloom is a CSS ::after pseudo-element on .hud-panel — no separate component.
 */

import type React from 'react';
import type { ReactElement, ReactNode } from 'react';
import '../hud.css';
import './HudPanel.css';
import './HudCornerBrackets.css';
import './HudLightTrace.css';

export type HudPanelVariant = 'default' | 'dev';

export interface HudPanelProps {
    /** Whether this panel is the currently focused window. */
    focused?: boolean;
    /** Visual variant — 'dev' uses warning border color. */
    variant?: HudPanelVariant;
    /** Icon node rendered in the header's .ix span (accent-bright color). */
    icon?: ReactNode;
    /** Title string rendered in the header's .tt span (text-secondary color). */
    title?: ReactNode;
    /**
     * Short text label (e.g. "LIVE", "NEW") placed at the end of the header row.
     * Rendered inside a .badge span with accent border + 8px font styling.
     */
    badge?: ReactNode;
    /**
     * ReactNode for buttons or icon controls placed after the badge.
     * Rendered inside .hud-panel__header-actions.
     */
    actions?: ReactNode;
    /**
     * When true, suppresses the decorative .dots element in the header.
     * Defaults to false — dots are always rendered when the header row renders.
     */
    hideDots?: boolean;
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
    badge,
    actions,
    hideDots = false,
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
        icon !== undefined || title !== undefined || badge !== undefined || actions !== undefined;

    return (
        <div className={panelClass} style={style}>
            {/* Corner brackets — 4 L-shaped marks, styled by parent .hud-panel state */}
            <span className="hud-corner-bracket tl" aria-hidden />
            <span className="hud-corner-bracket tr" aria-hidden />
            <span className="hud-corner-bracket bl" aria-hidden />
            <span className="hud-corner-bracket br" aria-hidden />

            {/* Light trace — thin strip circumnavigating the panel edges */}
            <span className="hud-light-trace" aria-hidden>
                <i className="hud-trace hud-trace--top" />
                <i className="hud-trace hud-trace--bottom" />
                <i className="hud-trace hud-trace--left" />
                <i className="hud-trace hud-trace--right" />
            </span>

            {/* Header row */}
            {hasHeader && (
                <div ref={headerRef} onClick={onHeaderClick} className="hud-panel__header">
                    {icon !== undefined && <span className="ix">{icon}</span>}
                    {title !== undefined && <span className="tt">{title}</span>}
                    {!hideDots && (
                        <span className="dots">
                            <i />
                            <i />
                            <i />
                        </span>
                    )}
                    {badge !== undefined && <span className="badge">{badge}</span>}
                    {actions !== undefined && (
                        <span className="hud-panel__header-actions">{actions}</span>
                    )}
                </div>
            )}

            {/* Content */}
            {children !== undefined && <div className="hud-panel__body">{children}</div>}
        </div>
    );
}

export default HudPanel;
