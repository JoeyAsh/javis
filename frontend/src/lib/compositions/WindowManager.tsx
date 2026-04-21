import { useCallback, useEffect, useRef, useState, type ReactElement, type ReactNode } from 'react';
import { Window } from '../primitives/Window';
import type { WindowState } from '../primitives/Window';
import { SnapOverlay } from '../primitives/SnapOverlay';
import { SwapOverlay } from '../primitives/SwapOverlay';
import { computeAllSlots } from '../layout/SlotGrid';
import type { SlotId, SlotRect } from '../layout/SlotGrid';
import './WindowManager.css';

export interface ManagedWindow {
    id: string;
    title?: ReactNode;
    ix?: ReactNode;
    badge?: ReactNode;
    content: ReactNode;
}

export interface WindowManagerProps {
    /** Windows to render. */
    windows: ManagedWindow[];
    /** windowId → slotId (controlled). */
    assignments: Record<string, SlotId>;
    /** Called when assignments should change (drop → move or swap). */
    onAssignmentsChange: (next: Record<string, SlotId>) => void;
    /** Focused window id (controlled). */
    focusedId?: string | null;
    /** Called when a window is focused / blur (null = no focus). */
    onFocusChange?: (id: string | null) => void;
    className?: string;
}

/** Internal per-drag state. */
interface ActiveDrag {
    windowId: string;
    /** Slot the dragged window was in at the start of the drag. */
    originSlot: SlotId;
}

/** Read-only viewport dimensions. */
interface ViewportSize {
    w: number;
    h: number;
}

function getViewport(): ViewportSize {
    return {
        w: typeof window !== 'undefined' ? window.innerWidth : 1280,
        h: typeof window !== 'undefined' ? window.innerHeight : 900,
    };
}

/**
 * WindowManager — controlled composition that renders N windows at slot-derived
 * positions, handles drag-to-snap and drag-to-swap, and fires
 * `onAssignmentsChange` on drop.
 *
 * All assignment state lives in the parent. Internal state covers only
 * the current drag (which window is dragging, snap target, swap target).
 */
export function WindowManager({
    windows,
    assignments,
    onAssignmentsChange,
    focusedId = null,
    onFocusChange,
    className,
}: WindowManagerProps): ReactElement {
    const [viewport, setViewport] = useState<ViewportSize>(getViewport);

    // Recompute on resize.
    useEffect(() => {
        const onResize = (): void => {
            setViewport(getViewport());
        };
        window.addEventListener('resize', onResize);
        return () => {
            window.removeEventListener('resize', onResize);
        };
    }, []);

    const slotRects = computeAllSlots(viewport.w, viewport.h);

    // Active drag state is internal — parent never needs to know mid-drag.
    const [activeDrag, setActiveDrag] = useState<ActiveDrag | null>(null);
    const [snapTarget, setSnapTarget] = useState<SlotId | null>(null);
    const [swapTarget, setSwapTarget] = useState<string | null>(null);

    // Keep assignments in a ref so event handlers never close over stale values.
    const assignmentsRef = useRef(assignments);
    assignmentsRef.current = assignments;

    /** Find which window (if any) occupies a slot, excluding the dragged window. */
    const windowAtSlot = useCallback((slotId: SlotId, excludeId: string): string | null => {
        for (const [wId, sId] of Object.entries(assignmentsRef.current)) {
            if (sId === slotId && wId !== excludeId) return wId;
        }
        return null;
    }, []);

    const handleFocus = useCallback(
        (id: string): void => {
            if (onFocusChange) onFocusChange(id);
        },
        [onFocusChange],
    );

    const handleDragStart = useCallback((id: string): void => {
        const origin = assignmentsRef.current[id] as SlotId | undefined;
        if (origin === undefined) return;
        setActiveDrag({ windowId: id, originSlot: origin });
        setSnapTarget(null);
        setSwapTarget(null);
    }, []);

    const handleDragMove = useCallback(
        (id: string, _dx: number, _dy: number, e: PointerEvent): void => {
            // Compute hovered slot from live pointer position.
            const rects = computeAllSlots(
                typeof window !== 'undefined' ? window.innerWidth : 1280,
                typeof window !== 'undefined' ? window.innerHeight : 900,
            );
            // Import slotAtPoint from layout to keep this clean.
            let hovered: SlotId | null = null;
            for (const [slotId, rect] of Object.entries(rects) as [SlotId, SlotRect][]) {
                if (
                    e.clientX >= rect.x &&
                    e.clientX <= rect.x + rect.w &&
                    e.clientY >= rect.y &&
                    e.clientY <= rect.y + rect.h
                ) {
                    hovered = slotId;
                    break;
                }
            }
            setSnapTarget(hovered);
            const swap = hovered !== null ? windowAtSlot(hovered, id) : null;
            setSwapTarget(swap);
        },
        [windowAtSlot],
    );

    const handleDragEnd = useCallback(
        (id: string, e: PointerEvent): void => {
            // Final slot under pointer.
            const rects = computeAllSlots(
                typeof window !== 'undefined' ? window.innerWidth : 1280,
                typeof window !== 'undefined' ? window.innerHeight : 900,
            );
            let hovered: SlotId | null = null;
            for (const [slotId, rect] of Object.entries(rects) as [SlotId, SlotRect][]) {
                if (
                    e.clientX >= rect.x &&
                    e.clientX <= rect.x + rect.w &&
                    e.clientY >= rect.y &&
                    e.clientY <= rect.y + rect.h
                ) {
                    hovered = slotId;
                    break;
                }
            }

            const current = assignmentsRef.current;
            const originSlot = current[id] as SlotId | undefined;

            if (hovered !== null && originSlot !== undefined) {
                const occupant = windowAtSlot(hovered, id);
                if (occupant !== null) {
                    // Swap: dragged → hovered slot, occupant → origin slot.
                    const next: Record<string, SlotId> = { ...current };
                    next[id] = hovered;
                    next[occupant] = originSlot;
                    onAssignmentsChange(next);
                } else if (hovered !== originSlot) {
                    // Move to empty slot.
                    const next: Record<string, SlotId> = { ...current };
                    next[id] = hovered;
                    onAssignmentsChange(next);
                }
                // else dropped on own slot — no change
            }
            // else dropped outside — snap back (no change)

            setActiveDrag(null);
            setSnapTarget(null);
            setSwapTarget(null);
        },
        [windowAtSlot, onAssignmentsChange],
    );

    // Click outside windows → clear focus.
    useEffect(() => {
        const onDocPointerDown = (e: PointerEvent): void => {
            const target = e.target as Element | null;
            if (!target) return;
            if (!target.closest('[data-window-id]')) {
                if (onFocusChange) onFocusChange(null);
            }
        };
        document.addEventListener('pointerdown', onDocPointerDown);
        return () => {
            document.removeEventListener('pointerdown', onDocPointerDown);
        };
    }, [onFocusChange]);

    const rootCls = ['lib-wm', className].filter(Boolean).join(' ');

    // Compute ghostRect for SwapOverlay: if swapTarget exists, show its current slot rect.
    const swapGhostRect: SlotRect | null =
        swapTarget !== null ? (slotRects[assignments[swapTarget] as SlotId] ?? null) : null;

    return (
        <div className={rootCls}>
            {windows.map((win) => {
                const slotId = assignments[win.id] as SlotId | undefined;
                if (slotId === undefined) return null;

                const rect = slotRects[slotId];
                const isDragging = activeDrag !== null && activeDrag.windowId === win.id;
                const isFocused = focusedId === win.id;

                let winState: WindowState = 'idle';
                if (isDragging) {
                    if (swapTarget !== null) {
                        winState = 'swap-preview';
                    } else if (snapTarget !== null) {
                        winState = 'snap-preview';
                    } else {
                        winState = 'dragging';
                    }
                } else if (isFocused) {
                    winState = 'focused';
                }

                return (
                    <Window
                        key={win.id}
                        id={win.id}
                        title={win.title}
                        ix={win.ix}
                        badge={win.badge}
                        position={rect}
                        state={winState}
                        focused={isFocused}
                        onFocus={handleFocus}
                        onDragStart={handleDragStart}
                        onDragMove={handleDragMove}
                        onDragEnd={handleDragEnd}
                        draggable={true}
                    >
                        {win.content}
                    </Window>
                );
            })}

            <SnapOverlay
                active={activeDrag !== null}
                slotRects={slotRects}
                hoveredSlot={snapTarget}
            />

            <SwapOverlay
                active={activeDrag !== null && swapTarget !== null}
                ghostRect={swapGhostRect}
                hovered={activeDrag !== null && swapTarget !== null}
            />
        </div>
    );
}

export default WindowManager;
