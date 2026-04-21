import { useCallback, useEffect, useRef } from 'react';
import type { SlotId } from '../components/hud/SlotGrid';

export interface UseSwapDragArgs {
    /** Swap-drag is only armed when the window is minimized. */
    enabled: boolean;
    /** Fired once, when pointer travel exceeds `threshold` from the pointerdown origin. */
    onSwapStart: () => void;
    /**
     * Fired during swap mode on each raw pointermove with viewport coordinates.
     * The consumer is responsible for resolving which slot (if any) is under the
     * cursor via `slotAtPoint` and rendering the visual feedback.
     */
    onSwapMove: (clientX: number, clientY: number) => void;
    /**
     * Fired on pointerup once a swap has been committed. `hoveredSlotId` is the
     * slot under the cursor at release time (null = dropped on empty space).
     */
    onSwapCommit: (hoveredSlotId: SlotId | null) => void;
    /** Fired on pointercancel or on release without having entered swap mode. */
    onSwapCancel: () => void;
    /** Function the hook calls at commit time to resolve the dropped-on slot. */
    resolveHoveredSlot: (clientX: number, clientY: number) => SlotId | null;
}

export interface UseSwapDragResult<T extends HTMLElement> {
    /** Attach to the drag handle (the window header). */
    handleRef: React.RefObject<T | null>;
    /** True while a swap is actively in progress. */
    isSwapping: () => boolean;
}

const DRAG_THRESHOLD_PX = 6;

/**
 * Pointer-based swap-drag hook. Arm it on a window header; it tracks
 * pointerdown → pointermove → pointerup and enters "swap mode" once the
 * pointer has travelled more than 6 px from the starting point. During swap
 * mode, the caller renders the dragged window's visual following the cursor
 * and the placeholder ghosts for all other slots.
 *
 * The hook does NOT write any DOM — it only reports events.
 */
export function useSwapDrag<T extends HTMLElement>({
    enabled,
    onSwapStart,
    onSwapMove,
    onSwapCommit,
    onSwapCancel,
    resolveHoveredSlot,
}: UseSwapDragArgs): UseSwapDragResult<T> {
    const handleRef = useRef<T | null>(null);
    const swappingRef = useRef(false);
    const pointerDownRef = useRef(false);
    const startRef = useRef({ x: 0, y: 0 });
    const pointerIdRef = useRef<number | null>(null);
    const lastPointRef = useRef({ x: 0, y: 0 });
    const rafRef = useRef<number | null>(null);

    // Keep latest callback references in a ref so we don't re-subscribe on every render.
    const cbRef = useRef({
        onSwapStart,
        onSwapMove,
        onSwapCommit,
        onSwapCancel,
        resolveHoveredSlot,
    });
    cbRef.current = {
        onSwapStart,
        onSwapMove,
        onSwapCommit,
        onSwapCancel,
        resolveHoveredSlot,
    };

    const flush = useCallback(() => {
        rafRef.current = null;
        if (!swappingRef.current) return;
        cbRef.current.onSwapMove(lastPointRef.current.x, lastPointRef.current.y);
    }, []);

    useEffect(() => {
        const el = handleRef.current;
        if (!el || !enabled) return;

        const onPointerDown = (e: PointerEvent): void => {
            if (e.button !== 0) return;
            const target = e.target as HTMLElement | null;
            if (target && target.closest('[data-no-drag]')) return;
            pointerDownRef.current = true;
            pointerIdRef.current = e.pointerId;
            startRef.current = { x: e.clientX, y: e.clientY };
            lastPointRef.current = { x: e.clientX, y: e.clientY };
            try {
                el.setPointerCapture(e.pointerId);
            } catch {
                // ignore
            }
            e.preventDefault();
        };

        const onPointerMove = (e: PointerEvent): void => {
            if (!pointerDownRef.current) return;
            if (pointerIdRef.current !== null && e.pointerId !== pointerIdRef.current) {
                return;
            }
            lastPointRef.current = { x: e.clientX, y: e.clientY };

            if (!swappingRef.current) {
                const dx = e.clientX - startRef.current.x;
                const dy = e.clientY - startRef.current.y;
                if (dx * dx + dy * dy >= DRAG_THRESHOLD_PX * DRAG_THRESHOLD_PX) {
                    swappingRef.current = true;
                    cbRef.current.onSwapStart();
                } else {
                    return;
                }
            }

            if (rafRef.current === null) {
                rafRef.current = window.requestAnimationFrame(flush);
            }
        };

        const finish = (e: PointerEvent, mode: 'commit' | 'cancel'): void => {
            if (!pointerDownRef.current) return;
            if (pointerIdRef.current !== null && e.pointerId !== pointerIdRef.current) {
                return;
            }
            const wasSwapping = swappingRef.current;
            pointerDownRef.current = false;
            swappingRef.current = false;
            pointerIdRef.current = null;
            if (rafRef.current !== null) {
                window.cancelAnimationFrame(rafRef.current);
                rafRef.current = null;
            }
            try {
                el.releasePointerCapture(e.pointerId);
            } catch {
                // ignore
            }
            if (!wasSwapping) {
                // Never entered swap mode — treat as a plain click; nothing to commit
                // or cancel. The caller's click handler (e.g. focus on pointerdown)
                // handles that path.
                return;
            }
            if (mode === 'commit') {
                const slot = cbRef.current.resolveHoveredSlot(e.clientX, e.clientY);
                cbRef.current.onSwapCommit(slot);
            } else {
                cbRef.current.onSwapCancel();
            }
        };

        const onPointerUp = (e: PointerEvent): void => finish(e, 'commit');
        const onPointerCancel = (e: PointerEvent): void => finish(e, 'cancel');

        el.addEventListener('pointerdown', onPointerDown);
        el.addEventListener('pointermove', onPointerMove);
        el.addEventListener('pointerup', onPointerUp);
        el.addEventListener('pointercancel', onPointerCancel);

        return () => {
            el.removeEventListener('pointerdown', onPointerDown);
            el.removeEventListener('pointermove', onPointerMove);
            el.removeEventListener('pointerup', onPointerUp);
            el.removeEventListener('pointercancel', onPointerCancel);
            if (rafRef.current !== null) {
                window.cancelAnimationFrame(rafRef.current);
                rafRef.current = null;
            }
            // Reset in case enabled flipped while an interaction was live.
            pointerDownRef.current = false;
            swappingRef.current = false;
            pointerIdRef.current = null;
        };
    }, [enabled, flush]);

    return {
        handleRef,
        isSwapping: () => swappingRef.current,
    };
}

export default useSwapDrag;
