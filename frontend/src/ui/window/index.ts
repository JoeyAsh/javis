// Window subsystem public barrel
export { Window } from './Window';
export type { WindowProps, WindowState, PanelMode, PanelContentRenderProps } from './Window';

export { SnapOverlay } from './SnapOverlay';
export type { SnapOverlayProps } from './SnapOverlay';

export { SwapOverlay } from './SwapOverlay';
export type { SwapOverlayProps } from './SwapOverlay';

export { SlotGhost } from './SlotGhost';
export type { SlotGhostProps } from './SlotGhost';

export {
    computeSlot,
    computeAllSlots,
    slotAtPoint,
    SLOT_IDS,
    TOP_BAR_HEIGHT,
    SLOT_MARGIN,
    COLUMN_WIDTH,
    BOTTOM_STRIP_HEIGHT,
} from './slotGrid';
export type { SlotId, SlotRect } from './slotGrid';

export { useDraggable } from './hooks/useDraggable';
export type { DragState, UseDraggableOptions } from './hooks/useDraggable';

export { useResizable } from './hooks/useResizable';
export type { ResizeDir, ResizeState, UseResizableOptions } from './hooks/useResizable';

export { useSlotDrag } from './hooks/useSlotDrag';
export type { SlotDragState, UseSlotDragOptions, WindowId } from './hooks/useSlotDrag';
