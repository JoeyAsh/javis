import type { CSSProperties, ReactElement } from 'react';
import type { SlotGhostProps } from './SlotGhost.types';

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
