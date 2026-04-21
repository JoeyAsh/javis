import { useCallback, useEffect, useRef } from 'react';

export interface UseDraggableArgs {
  /** Called with the final committed position when the pointer is released. */
  onMove: (x: number, y: number) => void;
  /** Optional live callback during drag (throttled via rAF). */
  onDrag?: (x: number, y: number) => void;
  /**
   * Optional callback fired on every raw pointermove during a drag with the
   * pointer's viewport coordinates. Unlike `onDrag` this is NOT rAF-throttled
   * and does NOT map to window position — it's meant for features that need
   * the raw pointer (e.g. snap-zone detection).
   */
  onPointerMove?: (clientX: number, clientY: number) => void;
  /** Optional callback fired once when the drag ends (pointerup / cancel). */
  onDragEnd?: () => void;
  /**
   * Optional callback fired once when a drag starts (pointer-down and drag
   * begins). Used by callers to trigger SFX without coupling the hook to any
   * audio subsystem directly.
   */
  onDragStart?: () => void;
  /**
   * Optional callback fired on pointerup AND pointercancel (drag end of any
   * kind). Distinct from `onDragEnd` which fires after position commit only.
   * Used by callers to trigger SFX for both committed and cancelled drags.
   */
  onDragStop?: () => void;
  /** Disable drag handling entirely. */
  disabled?: boolean;
  /** Getter for the current top-left position of the draggable element. */
  getPosition: () => { x: number; y: number };
}

export interface UseDraggableResult<T extends HTMLElement> {
  /** Attach to the drag-handle element (e.g. window header). */
  handleRef: React.RefObject<T | null>;
  /** Whether a drag is currently in progress. */
  isDragging: () => boolean;
}

/**
 * Pointer-based drag hook. Captures the pointer on the handle element and
 * commits the final position via `onMove` on pointerup. Live updates to the
 * DOM (transform translate) must be made by the caller inside `onDrag`.
 *
 * The hook never writes to the DOM itself — it only reports numbers.
 */
export function useDraggable<T extends HTMLElement>({
  onMove,
  onDrag,
  onPointerMove,
  onDragEnd,
  onDragStart,
  onDragStop,
  disabled = false,
  getPosition,
}: UseDraggableArgs): UseDraggableResult<T> {
  const handleRef = useRef<T | null>(null);
  const draggingRef = useRef(false);
  const startRef = useRef({ x: 0, y: 0, originX: 0, originY: 0 });
  const latestRef = useRef({ x: 0, y: 0 });
  const rafRef = useRef<number | null>(null);
  const pointerIdRef = useRef<number | null>(null);

  const flushDrag = useCallback(() => {
    rafRef.current = null;
    if (!draggingRef.current) return;
    if (onDrag) onDrag(latestRef.current.x, latestRef.current.y);
  }, [onDrag]);

  useEffect(() => {
    const el = handleRef.current;
    if (!el || disabled) return;

    const onPointerDown = (e: PointerEvent): void => {
      if (e.button !== 0) return;
      // Don't start a drag on interactive children (buttons, inputs, etc.)
      const target = e.target as HTMLElement | null;
      if (target && target.closest('[data-no-drag]')) return;
      const origin = getPosition();
      draggingRef.current = true;
      pointerIdRef.current = e.pointerId;
      startRef.current = {
        x: e.clientX,
        y: e.clientY,
        originX: origin.x,
        originY: origin.y,
      };
      latestRef.current = { x: origin.x, y: origin.y };
      try {
        el.setPointerCapture(e.pointerId);
      } catch {
        // older engines may throw; safe to ignore
      }
      e.preventDefault();
      if (onDragStart) onDragStart();
    };

    const handlePointerMove = (e: PointerEvent): void => {
      if (!draggingRef.current) return;
      if (pointerIdRef.current !== null && e.pointerId !== pointerIdRef.current) return;
      const dx = e.clientX - startRef.current.x;
      const dy = e.clientY - startRef.current.y;
      latestRef.current = {
        x: startRef.current.originX + dx,
        y: startRef.current.originY + dy,
      };
      if (onPointerMove) onPointerMove(e.clientX, e.clientY);
      if (rafRef.current === null) {
        rafRef.current = window.requestAnimationFrame(flushDrag);
      }
    };

    const endDrag = (e: PointerEvent, committed: boolean): void => {
      if (!draggingRef.current) return;
      if (pointerIdRef.current !== null && e.pointerId !== pointerIdRef.current) return;
      draggingRef.current = false;
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
      // Only commit the final position on a clean release. On cancellation
      // (Alt-Tab, blur, OS interrupt) we discard the in-flight drag so no
      // unexpected snap or teleport occurs.
      if (committed) {
        onMove(latestRef.current.x, latestRef.current.y);
      }
      if (onDragEnd) onDragEnd();
    };

    const onPointerUp = (e: PointerEvent): void => {
      if (draggingRef.current) {
        if (onDragStop) onDragStop();
      }
      endDrag(e, true);
    };
    const onPointerCancel = (e: PointerEvent): void => {
      if (draggingRef.current) {
        if (onDragStop) onDragStop();
      }
      endDrag(e, false);
    };

    el.addEventListener('pointerdown', onPointerDown);
    el.addEventListener('pointermove', handlePointerMove);
    el.addEventListener('pointerup', onPointerUp);
    el.addEventListener('pointercancel', onPointerCancel);

    return () => {
      el.removeEventListener('pointerdown', onPointerDown);
      el.removeEventListener('pointermove', handlePointerMove);
      el.removeEventListener('pointerup', onPointerUp);
      el.removeEventListener('pointercancel', onPointerCancel);
      if (rafRef.current !== null) {
        window.cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
    };
  }, [disabled, flushDrag, getPosition, onMove, onPointerMove, onDragEnd, onDragStart, onDragStop]);

  return {
    handleRef,
    isDragging: () => draggingRef.current,
  };
}

export default useDraggable;
