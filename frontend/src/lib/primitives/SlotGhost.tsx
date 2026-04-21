import type { CSSProperties, ReactElement } from 'react';
import type { SlotRect } from '../layout/SlotGrid';
import './SlotGhost.css';

export interface SlotGhostProps {
    /** Absolute rect of the slot (viewport-relative). */
    rect: SlotRect;
    /** Optional label text — e.g. slot id like "L1". */
    label?: string;
    className?: string;
}

/**
 * A standalone dashed rectangle that marks an empty slot position.
 * No interaction — purely decorative placeholder.
 */
export function SlotGhost({ rect, label, className }: SlotGhostProps): ReactElement {
    const style: CSSProperties = {
        left: rect.x,
        top: rect.y,
        width: rect.w,
        height: rect.h,
    };

    const rootCls = ['lib-slot-ghost', className].filter(Boolean).join(' ');

    return (
        <div className={rootCls} style={style} aria-hidden>
            {label !== undefined && <span className="lib-slot-ghost__label">{label}</span>}
        </div>
    );
}

export default SlotGhost;
