import type { CSSProperties, ReactElement } from 'react';
import type { PanelId } from '../../types';
import type { SlotId, SlotRect } from './SlotGrid';
import { SLOT_IDS } from './SlotGrid';

export interface SwapOverlayProps {
    /** Whether a swap-drag is currently in progress. */
    active: boolean;
    /** Pre-computed rects for every slot. */
    slotRects: Record<SlotId, SlotRect>;
    /** The slot currently under the cursor (null if none). */
    hoveredSlotId: SlotId | null;
    /** The slot id that the dragged window is coming FROM. */
    sourceSlotId: SlotId | null;
    /** Map slot id → resident panel id (for label rendering in ghosts). */
    residentBySlot: Partial<Record<SlotId, PanelId>>;
    /** Map panel id → display title. */
    titleByPanel: Record<PanelId, string>;
}

/**
 * Renders placeholder ghosts over every non-source slot while a swap-drag is
 * in progress. The dragged window's visual is handled by <SwapDragPreview/>;
 * this overlay only provides the drop-target feedback.
 */
export function SwapOverlay({
    active,
    slotRects,
    hoveredSlotId,
    sourceSlotId,
    residentBySlot,
    titleByPanel,
}: SwapOverlayProps): ReactElement {
    if (!active) {
        return <div className="swap-overlay" aria-hidden />;
    }
    return (
        <div className="swap-overlay swap-overlay--active" aria-hidden>
            {SLOT_IDS.map((slotId) => {
                if (slotId === sourceSlotId) return null;
                const rect = slotRects[slotId];
                const resident = residentBySlot[slotId];
                const isHovered = hoveredSlotId === slotId;
                const style: CSSProperties = {
                    left: rect.x,
                    top: rect.y,
                    width: rect.w,
                    height: rect.h,
                };
                const cls = ['swap-ghost', isHovered ? 'swap-ghost--hovered' : '']
                    .filter(Boolean)
                    .join(' ');
                return (
                    <div key={slotId} className={cls} style={style}>
                        <span className="swap-ghost-label">
                            {resident !== undefined ? titleByPanel[resident] : slotId}
                        </span>
                    </div>
                );
            })}
        </div>
    );
}

export default SwapOverlay;
