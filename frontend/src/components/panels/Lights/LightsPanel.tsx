/**
 * LightsPanel — Hypermodern HUD zone lighting control panel.
 *
 * STATUS: DORMANT — Sub-14. Backend wiring (Home Assistant integration) tracked
 * in issue #54. This component is registered in panels/index.ts but is NOT
 * included in the default HUD layout — see HudWindows.tsx for the exclusion.
 *
 * Design reference: .tmp/design_handoff_jarvis_hud/reference/JARVIS HUD Hypermodern.html
 * function LightsPanel (lines 790–820). Matches the 2-column zone tile grid,
 * toggle-on-click interaction, brightness bar, and dim label.
 *
 * Props contract (for backend follow-up #54):
 *   zones?    — Zone[] from Home Assistant via WS. Empty → placeholder shown.
 *   onAction? — Dispatcher for toggle / brightness / color actions.
 *   mode?     — 'compact' | 'expanded' from WindowManager.
 *
 * Mock data: 4 zones from MOCK_ZONES below (Living Room, Kitchen, Workshop, Bedroom).
 * Backend replaces mock with live zones from WS in issue #54.
 */

import { useState } from 'react';
import type { ReactElement } from 'react';
import './LightsPanel.css';
import { ZoneTile } from './ZoneTile';
import type { LightsPanelProps, Zone, ZoneAction } from './types';

// ---------------------------------------------------------------------------
// Mock data — 4 zones matching the Hypermodern HUD prototype exactly.
// Replaced by live Home Assistant data in backend follow-up #54.
// ---------------------------------------------------------------------------

const MOCK_ZONES: Zone[] = [
    { id: 'lr', label: 'Living Room', on: true, brightness: 72 },
    { id: 'kt', label: 'Kitchen', on: true, brightness: 45 },
    { id: 'wk', label: 'Workshop', on: false, brightness: 0 },
    { id: 'bd', label: 'Bedroom', on: false, brightness: 0 },
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function LightsPanel({
    zones,
    onAction,
    mode = 'expanded',
}: LightsPanelProps): ReactElement {
    // Local toggle state used when no external zones prop is provided (mock mode).
    // When zones are provided from the backend, this state is ignored and the
    // parent is responsible for reflecting toggle updates via the zones prop.
    const [localZones, setLocalZones] = useState<Zone[]>(MOCK_ZONES);

    const effectiveZones = zones ?? localZones;
    const hasZones = effectiveZones.length > 0;

    const handleAction = (zoneId: string, action: ZoneAction): void => {
        if (onAction !== undefined) {
            // Delegate to backend-wired dispatcher (issue #54)
            onAction(zoneId, action);
            return;
        }
        // Local mock toggle — only active when no external zones prop supplied
        if (zones === undefined && action.type === 'toggle') {
            setLocalZones((prev) =>
                prev.map((z) => {
                    if (z.id !== zoneId) return z;
                    const nowOn = !z.on;
                    return { ...z, on: nowOn, brightness: nowOn ? 60 : 0 };
                }),
            );
        }
    };

    if (!hasZones) {
        return (
            <div className="panel">
                <div className="lights-empty">NO ZONES — awaiting backend #54</div>
            </div>
        );
    }

    // Compact mode: show a summary count row + 2-column grid
    if (mode === 'compact') {
        const onCount = effectiveZones.filter((z) => z.on).length;
        return (
            <div className="panel">
                <div
                    style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 6,
                        padding: '4px 0 6px',
                        fontSize: 10,
                        color: 'var(--text-secondary)',
                        fontFamily: 'var(--font)',
                        letterSpacing: '0.05em',
                    }}
                >
                    <span style={{ color: 'var(--accent-bright)', fontWeight: 500 }}>
                        {effectiveZones.length}
                    </span>
                    <span>ZONES</span>
                    <span style={{ color: 'var(--text-muted)' }}>·</span>
                    <span style={{ color: 'var(--accent)', fontWeight: 500 }}>{onCount}</span>
                    <span>ON</span>
                </div>
                <div className="lights-grid">
                    {effectiveZones.map((zone) => (
                        <ZoneTile key={zone.id} zone={zone} onAction={handleAction} />
                    ))}
                </div>
            </div>
        );
    }

    // Expanded mode: full 2-column tile grid
    return (
        <div className="panel">
            <div className="lights-grid">
                {effectiveZones.map((zone) => (
                    <ZoneTile key={zone.id} zone={zone} onAction={handleAction} />
                ))}
            </div>
        </div>
    );
}

export default LightsPanel;
