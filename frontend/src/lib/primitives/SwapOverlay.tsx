import type { CSSProperties, ReactElement } from 'react';
import type { SlotRect } from '../layout/SlotGrid';
import './SwapOverlay.css';

export interface SwapOverlayProps {
    /** Whether a swap-eligible drag is currently in progress. */
    active: boolean;
    /**
     * Rect of the swap-target window in its *current* slot.
     * Shows where that window would land after the swap.
     */
    ghostRect: SlotRect | null;
    /** Whether the drag is positioned over the swap target's slot (confirms swap). */
    hovered?: boolean;
    className?: string;
}

/**
 * Renders a dashed ghost rectangle at the swap-target's current slot rect
 * while a drag is hovering an occupied slot.
 *
 * Positioned `fixed; inset:0; pointer-events:none`.
 */
export function SwapOverlay({
    active,
    ghostRect,
    hovered = false,
    className,
}: SwapOverlayProps): ReactElement {
    const rootCls = ['lib-swap', className].filter(Boolean).join(' ');

    if (!active || ghostRect === null) {
        return <div className={rootCls} aria-hidden />;
    }

    const style: CSSProperties = {
        left: ghostRect.x,
        top: ghostRect.y,
        width: ghostRect.w,
        height: ghostRect.h,
    };

    const ghostCls = ['lib-swap__ghost', hovered ? 'lib-swap__ghost--hovered' : '']
        .filter(Boolean)
        .join(' ');

    return (
        <div className={rootCls} aria-hidden>
            <div className={ghostCls} style={style} />
        </div>
    );
}

export default SwapOverlay;
