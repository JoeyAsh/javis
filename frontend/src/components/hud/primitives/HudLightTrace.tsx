/**
 * HudLightTrace — four animated accent-gradient strips along panel edges.
 *
 * Top: left-to-right (6 s). Bottom: right-to-left (delay −3 s).
 * Left: top-to-bottom (delay −4.5 s). Right: bottom-to-top (delay −1.5 s).
 * Opacity: .55 idle / .9 hover / 1 focused (driven by parent .hud-panel class).
 */

import type { ReactElement } from 'react';
import '../hud.css';
import './HudLightTrace.css';

export interface HudLightTraceProps {
    className?: string;
}

export function HudLightTrace({ className }: HudLightTraceProps): ReactElement {
    return (
        <div className={['hud-light-trace', className].filter(Boolean).join(' ')} aria-hidden>
            <span className="hud-trace hud-trace--top" />
            <span className="hud-trace hud-trace--bottom" />
            <span className="hud-trace hud-trace--left" />
            <span className="hud-trace hud-trace--right" />
        </div>
    );
}

export default HudLightTrace;
