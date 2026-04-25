import type { SlotRect } from '../slotGrid';

export interface SwapOverlayProps {
    active: boolean;
    ghostRect: SlotRect | null;
    hovered?: boolean;
    className?: string;
}
