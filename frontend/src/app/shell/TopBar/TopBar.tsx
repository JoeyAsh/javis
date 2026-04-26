/**
 * TopBar — JARVIS-specific top bar content.
 *
 * Left:   LINK·SECURE tag, clock, date, weather, coordinates.
 * Center: JARVIS / MK XLII brand mark.
 * Right:  controls cluster (idle toggle, reset, mic mute, sfx mute, settings).
 */

import type { ReactElement } from 'react';
import { TopBar as TopBarPrimitive } from '@ui';
import { useLocation } from '@common/hooks/useLocation';
import { DeviceBadge } from '@features/device';
import { WeatherWidget } from './WeatherWidget';
import { TimeWidget } from './TimeWidget';
import { ControlsCluster } from './ControlsCluster';
import styles from './TopBar.module.css';
import type { TopBarProps } from './TopBar.types';

export function TopBar({
    idle,
    onToggleIdle,
    onResetLayout,
    onOpenSettings,
    micMuted,
    onToggleMicMute,
    sfxMuted,
    onToggleSfxMute,
}: TopBarProps): ReactElement {
    const location = useLocation();
    const lat = location.coords.latitude;
    const lon = location.coords.longitude;
    const coordsLabel = `${lat >= 0 ? 'N' : 'S'} ${Math.abs(lat).toFixed(2)} · ${lon >= 0 ? 'E' : 'W'} ${Math.abs(lon).toFixed(2)}`;

    return (
        <TopBarPrimitive
            left={
                <div className={styles.left}>
                    <span className={styles.tag} aria-label="Link secure">
                        <span className={styles.tagDot} aria-hidden="true" />
                        LINK · SECURE
                    </span>
                    <DeviceBadge />
                    <span className={styles.sep} aria-hidden="true">◆</span>
                    <TimeWidget />
                    <span className={styles.sep} aria-hidden="true">·</span>
                    <WeatherWidget latitude={lat} longitude={lon} />
                    <span className={styles.sep} aria-hidden="true">·</span>
                    <span className={styles.coords} aria-label="Location coordinates">
                        {coordsLabel}
                    </span>
                </div>
            }
            center={
                <div className={styles.brand} aria-label="JARVIS Mark 42">
                    <b className={styles.brandJ}>J</b> A R V I S{' '}
                    <span className={styles.brandMk}>/ MK XLII</span>
                </div>
            }
            right={
                <ControlsCluster
                    idle={idle}
                    onToggleIdle={onToggleIdle}
                    onResetLayout={onResetLayout}
                    onOpenSettings={onOpenSettings}
                    micMuted={micMuted}
                    onToggleMicMute={onToggleMicMute}
                    sfxMuted={sfxMuted}
                    onToggleSfxMute={onToggleSfxMute}
                />
            }
        />
    );
}

export default TopBar;
