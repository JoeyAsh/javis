/**
 * ZoneTile — a single zone row/tile in the LightsPanel grid.
 *
 * Matches the Hypermodern HUD design from .tmp/design_handoff_jarvis_hud/reference/JARVIS HUD Hypermodern.html
 * lines 790–820: `.lt` / `.lt.on` / `.nm` / `.bb` / `.br` / `.dim` structure.
 *
 * Visual states:
 *   - Off: `--border` hairline, muted status dot, brightness bar at 0 %, "AUS" dim label
 *   - On:  `--accent` border + glow-inner, bright status dot with glow, brightness bar filled
 *
 * Click on the tile toggles on/off (dispatches `{ type: 'toggle' }` action).
 */

import type { ReactElement } from 'react';
import type { Zone, ZoneAction } from './types';

export interface ZoneTileProps {
    zone: Zone;
    /** Called when the user interacts with the tile. Undefined → tile is display-only. */
    onAction?: (zoneId: string, action: ZoneAction) => void;
}

export function ZoneTile({ zone, onAction }: ZoneTileProps): ReactElement {
    const handleClick = (): void => {
        onAction?.(zone.id, { type: 'toggle' });
    };

    const tileClass = ['zone-tile', zone.on ? 'zone-tile--on' : ''].filter(Boolean).join(' ');

    const barWidth = zone.on ? zone.brightness : 0;

    return (
        <div
            className={tileClass}
            onClick={handleClick}
            role="button"
            aria-label={`${zone.label}, ${zone.on ? 'on' : 'off'}`}
            aria-pressed={zone.on}
            tabIndex={0}
            onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    handleClick();
                }
            }}
            data-no-drag
        >
            <div className="zone-tile__row1">
                <span className="zone-tile__name">{zone.label}</span>
                <span className="zone-tile__dot" aria-hidden />
            </div>
            <div className="zone-tile__bar" aria-hidden>
                <i className="zone-tile__bar-fill" style={{ width: `${barWidth}%` }} />
            </div>
            <div className="zone-tile__dim">{zone.on ? `${zone.brightness} %` : 'AUS'}</div>
        </div>
    );
}

export default ZoneTile;
