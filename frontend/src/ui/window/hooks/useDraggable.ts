import { useCallback, useEffect, useRef, useState } from 'react';
import type React from 'react';
import { useSfx } from '@core/audio';

export interface DragState {
    dragging: boolean;
    startX: number;
    startY: number;
    dx: number;
    dy: number;
}

export interface UseDraggableOptions {
    onStart?: (e: PointerEvent) => void;
    onMove?: (state: DragState, e: PointerEvent) => void;
    onEnd?: (state: DragState, e: PointerEvent) => void;
    disabled?: boolean;
}

/**
 * Raw pointer-drag hook.
 *
 * Attaches pointer listeners on pointerdown and registers window-level
 * pointermove/pointerup inside the gesture so drag-outside-element works.
 * Uses pointer capture to prevent pointer loss when cursor leaves the element.
 *
 * Plays `drag_start` + starts `drag_move` loop on drag begin.
 * Stops `drag_move` loop + plays `drag_end` on drag end.
 *
 * Returns `onPointerDown` to attach to the drag handle and the current
 * `dragging` boolean for CSS state.
 */
export function useDraggable(options: UseDraggableOptions): {
    onPointerDown: (e: React.PointerEvent) => void;
    dragging: boolean;
} {
    const { onStart, onMove, onEnd, disabled = false } = options;
    const { playOneShot, play, stop } = useSfx();

    const [dragging, setDragging] = useState(false);
    const stateRef = useRef<DragState>({
        dragging: false,
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

    const playOneShotRef = useRef(playOneShot);
    const playRef = useRef(play);
    const stopRef = useRef(stop);
    playOneShotRef.current = playOneShot;
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
        (e: React.PointerEvent) => {
            if (disabled) return;
            if (e.button !== 0) return;
            const target = e.target as HTMLElement | null;
            if (target && target.closest('[data-no-drag]')) return;

            const currentTarget = e.currentTarget as HTMLElement;
            try {
                currentTarget.setPointerCapture(e.pointerId);
            } catch {
                // some engines may reject — safe to ignore
            }

            pointerIdRef.current = e.pointerId;
            const state: DragState = {
                dragging: true,
                startX: e.clientX,
                startY: e.clientY,
                dx: 0,
                dy: 0,
            };
            stateRef.current = state;
            setDragging(true);

            const nativeEvent = e.nativeEvent;
            playOneShotRef.current('drag_start');
            playRef.current('drag_move');
            if (onStartRef.current) onStartRef.current(nativeEvent);

            const handleMove = (ev: PointerEvent): void => {
                if (pointerIdRef.current !== null && ev.pointerId !== pointerIdRef.current) return;
                const next: DragState = {
                    ...stateRef.current,
                    dx: ev.clientX - stateRef.current.startX,
                    dy: ev.clientY - stateRef.current.startY,
                };
                stateRef.current = next;
                if (onMoveRef.current) onMoveRef.current(next, ev);
            };

            const handleUp = (ev: PointerEvent): void => {
                if (pointerIdRef.current !== null && ev.pointerId !== pointerIdRef.current) return;
                cleanup();
                const finalState: DragState = { ...stateRef.current, dragging: false };
                stateRef.current = finalState;
                setDragging(false);
                stopRef.current('drag_move');
                playOneShotRef.current('drag_end');
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

            e.preventDefault();
        },
        [disabled],
    );

    return { onPointerDown, dragging };
}

export default useDraggable;
