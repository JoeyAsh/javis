import { useCallback, useRef, useState } from 'react';
import type React from 'react';
import { useDraggable } from './useDraggable';
import type { DragState } from './useDraggable';
import { computeAllSlots, slotAtPoint } from '../layout/SlotGrid';
import type { SlotId } from '../layout/SlotGrid';

/** String alias for a window identifier. */
export type WindowId = string;

export interface SlotDragState {
    /** Whether a drag is currently in progress. */
    dragging: boolean;
    /** The slot currently being hovered (null if cursor is outside all slots). */
    snapTarget: SlotId | null;
    /**
     * If snapTarget is occupied by another window, the id of that window.
     * Null when snapTarget is empty or no drag is active.
     */
    swapTarget: WindowId | null;
    /** Horizontal delta from drag start in pixels. */
    dx: number;
    /** Vertical delta from drag start in pixels. */
    dy: number;
}

export interface UseSlotDragOptions {
    /** Id of the window being dragged. */
    windowId: WindowId;
    /** Current assignments: windowId → slotId. */
    assignments: Record<WindowId, SlotId>;
    /** Viewport width — used to compute slot rects. */
    viewportW: number;
    /** Viewport height — used to compute slot rects. */
    viewportH: number;
    /** Called when the drag begins. */
    onDragStart?: (windowId: WindowId, e: PointerEvent) => void;
    /** Called on every pointermove with live dx/dy and current snap/swap targets. */
    onDragMove?: (windowId: WindowId, state: SlotDragState, e: PointerEvent) => void;
    /** Called on pointerup. Final snapTarget is the resolved drop slot (may be null). */
    onDragEnd?: (windowId: WindowId, state: SlotDragState, e: PointerEvent) => void;
    /** Disable drag entirely. */
    disabled?: boolean;
}

/**
 * Higher-level drag hook that computes snap + swap targets as the user drags.
 *
 * Internally wraps `useDraggable` and calls `computeAllSlots` + `slotAtPoint`
 * on every pointermove. The parent is responsible for calling
 * `computeAllSlots` to obtain rects when needed (this hook recomputes on
 * every move to avoid stale rects on resize).
 */
export function useSlotDrag(options: UseSlotDragOptions): {
    onPointerDown: (e: React.PointerEvent) => void;
    slotDragState: SlotDragState;
} {
    const {
        windowId,
        assignments,
        viewportW,
        viewportH,
        onDragStart,
        onDragMove,
        onDragEnd,
        disabled = false,
    } = options;

    const [slotDragState, setSlotDragState] = useState<SlotDragState>({
        dragging: false,
        snapTarget: null,
        swapTarget: null,
        dx: 0,
        dy: 0,
    });

    // Keep references stable for callbacks.
    const assignmentsRef = useRef(assignments);
    const vpWRef = useRef(viewportW);
    const vpHRef = useRef(viewportH);
    assignmentsRef.current = assignments;
    vpWRef.current = viewportW;
    vpHRef.current = viewportH;

    const onDragStartRef = useRef(onDragStart);
    const onDragMoveRef = useRef(onDragMove);
    const onDragEndRef = useRef(onDragEnd);
    onDragStartRef.current = onDragStart;
    onDragMoveRef.current = onDragMove;
    onDragEndRef.current = onDragEnd;

    /** Derive which window (if any) occupies a given slot. */
    const windowAtSlot = useCallback((slotId: SlotId): WindowId | null => {
        for (const [wId, sId] of Object.entries(assignmentsRef.current)) {
            if (sId === slotId && wId !== windowId) {
                return wId;
            }
        }
        return null;
        // windowId captured by closure but does not change per hook instance
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const handleStart = useCallback(
        (e: PointerEvent): void => {
            setSlotDragState({ dragging: true, snapTarget: null, swapTarget: null, dx: 0, dy: 0 });
            if (onDragStartRef.current) onDragStartRef.current(windowId, e);
        },
        [windowId],
    );

    const handleMove = useCallback(
        (dragState: DragState, e: PointerEvent): void => {
            const rects = computeAllSlots(vpWRef.current, vpHRef.current);
            const hovered = slotAtPoint(e.clientX, e.clientY, rects);
            const swap = hovered !== null ? windowAtSlot(hovered) : null;
            const next: SlotDragState = {
                dragging: true,
                snapTarget: hovered,
                swapTarget: swap,
                dx: dragState.dx,
                dy: dragState.dy,
            };
            setSlotDragState(next);
            if (onDragMoveRef.current) onDragMoveRef.current(windowId, next, e);
        },
        [windowId, windowAtSlot],
    );

    const handleEnd = useCallback(
        (dragState: DragState, e: PointerEvent): void => {
            const rects = computeAllSlots(vpWRef.current, vpHRef.current);
            const hovered = slotAtPoint(e.clientX, e.clientY, rects);
            const swap = hovered !== null ? windowAtSlot(hovered) : null;
            const final: SlotDragState = {
                dragging: false,
                snapTarget: hovered,
                swapTarget: swap,
                dx: dragState.dx,
                dy: dragState.dy,
            };
            setSlotDragState({ dragging: false, snapTarget: null, swapTarget: null, dx: 0, dy: 0 });
            if (onDragEndRef.current) onDragEndRef.current(windowId, final, e);
        },
        [windowId, windowAtSlot],
    );

    const { onPointerDown } = useDraggable({
        onStart: handleStart,
        onMove: handleMove,
        onEnd: handleEnd,
        disabled,
    });

    return { onPointerDown, slotDragState };
}

export default useSlotDrag;
