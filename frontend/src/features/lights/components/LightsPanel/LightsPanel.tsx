/**
 * LightsPanel — Hypermodern HUD zone lighting control panel.
 *
 * STATUS: DORMANT — awaiting backend #54 (Home Assistant integration).
 * Registered in panels but NOT included in the default HUD layout.
 */
import { useState } from 'react';
import type { ReactElement } from 'react';
import { ZoneTile } from '../ZoneTile';
import { MOCK_ZONES } from '../../mock';
import type { Zone, ZoneAction } from '../../types';
import type { LightsPanelProps } from './LightsPanel.types';
import styles from './LightsPanel.module.css';

export function LightsPanel({
    zones,
    onAction,
    mode = 'expanded',
}: LightsPanelProps): ReactElement {
    // Local toggle state used when no external zones prop is provided (mock mode).
    const [localZones, setLocalZones] = useState<Zone[]>(MOCK_ZONES);

    const effectiveZones = zones ?? localZones;
    const hasZones = effectiveZones.length > 0;

    const handleAction = (zoneId: string, action: ZoneAction): void => {
        if (onAction !== undefined) {
            onAction(zoneId, action);
            return;
        }
        // Local mock toggle — only when no external zones prop supplied
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
            <div className={styles.panel}>
                <div className={styles.empty}>NO ZONES — awaiting backend #54</div>
            </div>
        );
    }

    if (mode === 'compact') {
        const onCount = effectiveZones.filter((z) => z.on).length;
        return (
            <div className={styles.panel}>
                <div className={styles.compactSummary}>
                    <span className={styles.summaryTotal}>{effectiveZones.length}</span>
                    <span>ZONES</span>
                    <span className={styles.summarySep}>·</span>
                    <span className={styles.summaryOn}>{onCount}</span>
                    <span>ON</span>
                </div>
                <div className={styles.grid}>
                    {effectiveZones.map((zone) => (
                        <ZoneTile key={zone.id} zone={zone} onAction={handleAction} />
                    ))}
                </div>
            </div>
        );
    }

    return (
        <div className={styles.panel}>
            <div className={styles.grid}>
                {effectiveZones.map((zone) => (
                    <ZoneTile key={zone.id} zone={zone} onAction={handleAction} />
                ))}
            </div>
        </div>
    );
}

export default LightsPanel;
