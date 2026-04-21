import type { CSSProperties, ReactElement } from 'react';
import type { SlotId, SlotRect } from '../layout/SlotGrid';
import { SLOT_IDS } from '../layout/SlotGrid';
import './SnapOverlay.css';

export interface SnapOverlayProps {
    /** Whether a drag is currently active (shows all slot zones). */
    active: boolean;
    /** Pre-computed rects for all 9 slots. */
    slotRects: Record<SlotId, SlotRect>;
    /** The slot currently hovered — receives highlight treatment. */
    hoveredSlot: SlotId | null;
    className?: string;
}

/**
 * Renders a semi-transparent zone rectangle over every slot while a drag is
 * active. The hovered slot receives a stronger fill + pulse animation.
 *
 * Positioned `fixed; inset:0; pointer-events:none` so it sits above all
 * content without capturing pointer events.
 */
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
            {SLOT_IDS.map((slotId) => {
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
