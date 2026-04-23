import { type ReactElement } from 'react';
import { Scene } from '../../primitives/Scene';
import { Reactor } from '../../primitives/Reactor';
import { ViewportCorners } from '../../primitives/ViewportCorners';
import type { HUDShellProps } from './HUDShell.types';
import './HUDShell.css';

export function HUDShell({
    topbar,
    orb,
    dock,
    scene,
    viewportCorners = true,
    reactor = true,
    idle = false,
    working = false,
    children,
    className,
    style,
}: HUDShellProps): ReactElement {
    const classes = ['hud-shell', idle && 'idle', working && 'is-working', className]
        .filter(Boolean)
        .join(' ');

    return (
        <div className={classes} style={style}>
            {/* Background scene layer */}
            <Scene grid={scene?.grid} stars={scene?.stars} scanlines={scene?.scanlines} />

            {/* Bottom reactor glow */}
            {reactor && <Reactor />}

            {/* Viewport corner marks */}
            {viewportCorners && <ViewportCorners />}

            {/* TopBar slot */}
            {topbar && <div className="hud-shell__topbar">{topbar}</div>}

            {/* Orb slot */}
            {orb && <div className="hud-shell__orb">{orb}</div>}

            {/* Panel / window slot */}
            {children && <div className="hud-shell__children">{children}</div>}

            {/* Dock slot (rendered at natural fixed position) */}
            {dock}
        </div>
    );
}

export default HUDShell;
