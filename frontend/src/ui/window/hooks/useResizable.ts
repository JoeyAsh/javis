import { useCallback, useEffect, useRef, useState } from 'react';
import type React from 'react';
import { useSfx } from '@core/audio';

export type ResizeDir = 'n' | 's' | 'e' | 'w' | 'ne' | 'nw' | 'se' | 'sw';

export interface ResizeState {
    resizing: boolean;
    dir: ResizeDir | null;
    startX: number;
    startY: number;
    dx: number;
    dy: number;
}

export interface UseResizableOptions {
    onStart?: (dir: ResizeDir, e: PointerEvent) => void;
    onMove?: (state: ResizeState, e: PointerEvent) => void;
    onEnd?: (state: ResizeState, e: PointerEvent) => void;
    disabled?: boolean;
}

/**
 * Raw pointer-resize hook.
 *
 * Returns `onPointerDown(dir)` factory that attaches pointer capture and
 * window-level pointermove/pointerup listeners for a resize gesture.
 *
 * Plays `resize` loop on resize start. Stops `resize` loop on resize end.
 */
export function useResizable(options: UseResizableOptions): {
    onPointerDown: (dir: ResizeDir) => (e: React.PointerEvent) => void;
    resizing: boolean;
    dir: ResizeDir | null;
} {
    const { onStart, onMove, onEnd, disabled = false } = options;
    const { play, stop } = useSfx();

    const [resizing, setResizing] = useState(false);
    const [activeDir, setActiveDir] = useState<ResizeDir | null>(null);

    const stateRef = useRef<ResizeState>({
        resizing: false,
        dir: null,
        startX: 0,
        startY: 0,
        dx: 0,
        dy: 0,
    });
    const pointerIdRef = useRef<number | null>(null);
    const cleanupRef = useRef<(() => void) | null>(null);

    const onStartRef = useRef(onStart);
    const onMoveRef = useRef(onMove);
    const onEndRef = useRef(onEnd);
    onStartRef.current = onStart;
    onMoveRef.current = onMove;
    onEndRef.current = onEnd;

    const playRef = useRef(play);
    const stopRef = useRef(stop);
    playRef.current = play;
    stopRef.current = stop;

    useEffect(() => {
        return () => {
            if (cleanupRef.current) {
                cleanupRef.current();
                cleanupRef.current = null;
            }
        };
    }, []);

    const onPointerDown = useCallback(
        (dir: ResizeDir) =>
            (e: React.PointerEvent): void => {
                if (disabled) return;
                if (e.button !== 0) return;

                e.stopPropagation();
                e.preventDefault();

                const currentTarget = e.currentTarget as HTMLElement;
                try {
                    currentTarget.setPointerCapture(e.pointerId);
                } catch {
                    // some engines may reject — safe to ignore
                }

                pointerIdRef.current = e.pointerId;

                const state: ResizeState = {
                    resizing: true,
                    dir,
                    startX: e.clientX,
                    startY: e.clientY,
                    dx: 0,
                    dy: 0,
                };
                stateRef.current = state;
                setResizing(true);
                setActiveDir(dir);

                playRef.current('resize');

                const nativeEvent = e.nativeEvent;
                if (onStartRef.current) onStartRef.current(dir, nativeEvent);

                const handleMove = (ev: PointerEvent): void => {
                    if (pointerIdRef.current !== null && ev.pointerId !== pointerIdRef.current)
                        return;
                    const next: ResizeState = {
                        ...stateRef.current,
                        dx: ev.clientX - stateRef.current.startX,
                        dy: ev.clientY - stateRef.current.startY,
                    };
                    stateRef.current = next;
                    if (onMoveRef.current) onMoveRef.current(next, ev);
                };

                const handleUp = (ev: PointerEvent): void => {
                    if (pointerIdRef.current !== null && ev.pointerId !== pointerIdRef.current)
                        return;
                    cleanup();
                    const finalState: ResizeState = { ...stateRef.current, resizing: false };
                    stateRef.current = finalState;
                    setResizing(false);
                    setActiveDir(null);
                    stopRef.current('resize');
                    if (onEndRef.current) onEndRef.current(finalState, ev);
                };

                const cleanup = (): void => {
                    window.removeEventListener('pointermove', handleMove);
                    window.removeEventListener('pointerup', handleUp);
                    window.removeEventListener('pointercancel', handleUp);
                    pointerIdRef.current = null;
                    cleanupRef.current = null;
                };

                cleanupRef.current = cleanup;

                window.addEventListener('pointermove', handleMove);
                window.addEventListener('pointerup', handleUp);
                window.addEventListener('pointercancel', handleUp);
            },
        [disabled],
    );

    return { onPointerDown, resizing, dir: activeDir };
}

export default useResizable;
