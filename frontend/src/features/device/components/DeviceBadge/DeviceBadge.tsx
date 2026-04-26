import type { ReactElement } from 'react';
import { useDevice } from '../../hooks/useDevice';
import type { DeviceBadgeProps } from './DeviceBadge.types';

/**
 * DeviceBadge — renders a compact HUD pill showing the current device slug.
 *
 * Returns null until the backend has pushed a `device_info` WS message so
 * that the TopBar layout does not shift on cold-boot.
 */
export function DeviceBadge(_props: DeviceBadgeProps): ReactElement | null {
    const { slug, received } = useDevice();

    if (!received) {
        return null;
    }

    return (
        <span
            className="inline-flex items-center gap-[3px] rounded-[2px] border border-[var(--border)] px-[5px] py-[1px] font-mono text-[9px] uppercase tracking-[1px] text-[var(--text-muted)] select-none"
            aria-label={`Active device: ${slug}`}
        >
            {slug}
        </span>
    );
}

export default DeviceBadge;
