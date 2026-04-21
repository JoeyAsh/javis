import { useCallback, useEffect, useRef } from 'react';

export interface UseResizableArgs {
    /** Called with the final width/height when the pointer is released. */
    onResize: (w: number, h: number) => void;
    /** Optional live callback during resize (throttled via rAF). */
    onResizing?: (w: number, h: number) => void;
    /**
     * Optional callback fired once on pointerup (resize committed). NOT fired
     * during live resizing. Used by callers to trigger SFX without coupling the
     * hook to any audio subsystem directly.
     */
    onResizeEnd?: () => void;
    /** Getter for the current width/height of the resizable element. */
    getSize: () => { w: number; h: number };
    /** Disable resize handling entirely. */
    disabled?: boolean;
    minW?: number;
    minH?: number;
    maxW?: number;
    maxH?: number;
}

export interface UseResizableResult<T extends HTMLElement> {
    /** Attach to the resize handle element (e.g. bottom-right corner). */
    handleRef: React.RefObject<T | null>;
    isResizing: () => boolean;
}

const DEFAULT_MIN_W = 160;
const DEFAULT_MIN_H = 80;

/**
 * Pointer-based resize hook. Captures the pointer on a corner handle and
 * reports w/h via `onResize` on pointerup. Live size is provided via
 * `onResizing` during drag.
 */
export function useResizable<T extends HTMLElement>({
    onResize,
    onResizing,
    onResizeEnd,
    getSize,
    disabled = false,
    minW = DEFAULT_MIN_W,
    minH = DEFAULT_MIN_H,
    maxW,
    maxH,
}: UseResizableArgs): UseResizableResult<T> {
    const handleRef = useRef<T | null>(null);
    const resizingRef = useRef(false);
    const startRef = useRef({ x: 0, y: 0, originW: 0, originH: 0 });
    const latestRef = useRef({ w: 0, h: 0 });
    const rafRef = useRef<number | null>(null);
    const pointerIdRef = useRef<number | null>(null);

    const flush = useCallback(() => {
        rafRef.current = null;
        if (!resizingRef.current) return;
        if (onResizing) onResizing(latestRef.current.w, latestRef.current.h);
    }, [onResizing]);

    useEffect(() => {
        const el = handleRef.current;
        if (!el || disabled) return;

        const clamp = (w: number, h: number): { w: number; h: number } => {
            const effMaxW = maxW ?? window.innerWidth;
            const effMaxH = maxH ?? window.innerHeight;
            return {
                w: Math.max(minW, Math.min(effMaxW, w)),
                h: Math.max(minH, Math.min(effMaxH, h)),
            };
        };

        const onPointerDown = (e: PointerEvent): void => {
            if (e.button !== 0) return;
            const size = getSize();
            resizingRef.current = true;
            pointerIdRef.current = e.pointerId;
            startRef.current = {
                x: e.clientX,
                y: e.clientY,
                originW: size.w,
                originH: size.h,
            };
            latestRef.current = { w: size.w, h: size.h };
            try {
                el.setPointerCapture(e.pointerId);
            } catch {
                // ignore
            }
            e.preventDefault();
            e.stopPropagation();
        };

        const onPointerMove = (e: PointerEvent): void => {
            if (!resizingRef.current) return;
            if (pointerIdRef.current !== null && e.pointerId !== pointerIdRef.current) return;
            const dw = e.clientX - startRef.current.x;
            const dh = e.clientY - startRef.current.y;
            const clamped = clamp(startRef.current.originW + dw, startRef.current.originH + dh);
            latestRef.current = clamped;
            if (rafRef.current === null) {
                rafRef.current = window.requestAnimationFrame(flush);
            }
        };

        const endResize = (e: PointerEvent): void => {
            if (!resizingRef.current) return;
            if (pointerIdRef.current !== null && e.pointerId !== pointerIdRef.current) return;
            resizingRef.current = false;
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
            onResize(latestRef.current.w, latestRef.current.h);
            if (onResizeEnd) onResizeEnd();
        };

        el.addEventListener('pointerdown', onPointerDown);
        el.addEventListener('pointermove', onPointerMove);
        el.addEventListener('pointerup', endResize);
        el.addEventListener('pointercancel', endResize);

        return () => {
            el.removeEventListener('pointerdown', onPointerDown);
            el.removeEventListener('pointermove', onPointerMove);
            el.removeEventListener('pointerup', endResize);
            el.removeEventListener('pointercancel', endResize);
            if (rafRef.current !== null) {
                window.cancelAnimationFrame(rafRef.current);
                rafRef.current = null;
            }
        };
    }, [disabled, flush, getSize, maxH, maxW, minH, minW, onResize, onResizeEnd]);

    return {
        handleRef,
        isResizing: () => resizingRef.current,
    };
}

export default useResizable;
