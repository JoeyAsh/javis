import type { SlotId, SlotRect } from '../slotGrid';

export interface SnapOverlayProps {
    active: boolean;
    slotRects: Record<SlotId, SlotRect>;
    hoveredSlot: SlotId | null;
    className?: string;
}
