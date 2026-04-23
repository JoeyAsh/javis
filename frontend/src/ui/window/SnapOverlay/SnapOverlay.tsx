import type { CSSProperties, ReactElement } from 'react';
import type { SlotId } from '../slotGrid';
import { SLOT_IDS } from '../slotGrid';
import type { SnapOverlayProps } from './SnapOverlay.types';
import './SnapOverlay.css';

export function SnapOverlay({
    active,
    slotRects,
    hoveredSlot,
    className,
}: SnapOverlayProps): ReactElement {
    const rootCls = ['lib-snap', className].filter(Boolean).join(' ');

    if (!active) {
        return <div className={rootCls} aria-hidden />;
    }

    return (
        <div className={rootCls} aria-hidden>
            {SLOT_IDS.map((slotId: SlotId) => {
                const rect = slotRects[slotId];
                const isHovered = hoveredSlot === slotId;
                const style: CSSProperties = {
                    left: rect.x,
                    top: rect.y,
                    width: rect.w,
                    height: rect.h,
                };
                const cls = ['lib-snap__zone', isHovered ? 'lib-snap__zone--hovered' : '']
                    .filter(Boolean)
                    .join(' ');
                return <div key={slotId} className={cls} style={style} data-slot={slotId} />;
            })}
        </div>
    );
}

export default SnapOverlay;
