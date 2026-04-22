import { useCallback, useMemo, useRef, useState } from 'react';
import type {
  CSSProperties,
  MouseEvent as ReactMouseEvent,
  PointerEvent as ReactPointerEvent,
  ReactNode,
  ReactElement,
} from 'react';
import type { PanelId, PanelMode } from '../../types';
import { detectSnapRegion, useWindowManager } from './WindowManager';
import type { SnapRegion } from './WindowManager';
import type { SlotId } from './SlotGrid';
import { slotAtPoint } from './SlotGrid';
import { useDraggable } from '../../hooks/useDraggable';
import { useResizable } from '../../hooks/useResizable';
import { useSwapDrag } from '../../hooks/useSwapDrag';

export interface WindowProps {
  id: PanelId;
  title: string;
  icon?: ReactNode;
  /** Callback receives the active mode so the same body can adapt. */
  children: (mode: PanelMode) => ReactNode;
  /** Disable window interactions (used by idle mode). */
  disabled?: boolean;
  /** Called when the user starts a swap drag on this (minimized) window. */
  onSwapStart?: (id: PanelId) => void;
  /** Called with live cursor coords while a swap drag is in progress. */
  onSwapMove?: (clientX: number, clientY: number) => void;
  /**
   * Called when the swap drag ends. `targetSlotId` is the slot under the
   * cursor at release time (null = dropped on empty space).
   */
  onSwapCommit?: (id: PanelId, targetSlotId: SlotId | null) => void;
  /** Called when the swap drag is cancelled (pointercancel, etc.). */
  onSwapCancel?: () => void;
}

const DOUBLE_CLICK_MS = 300;

export function Window({
  id,
  title,
  icon,
  children,
  disabled = false,
  onSwapStart,
  onSwapMove,
  onSwapCommit,
  onSwapCancel,
}: WindowProps): ReactElement {
  const {
    windows,
    focusedId,
    settlingIds,
    slotRects,
    focus,
    move,
    resize,
    minimize,
    maximize,
    toggleMaximize,
    resetWindow,
    setActiveSnap,
    snapWindow,
  } = useWindowManager();
  const state = windows[id];

  // Live-drag position / size (only used while maximized & actively dragging).
  const [livePos, setLivePos] = useState<{ x: number; y: number } | null>(null);
  const [liveSize, setLiveSize] = useState<{ w: number; h: number } | null>(null);
  // True while a swap-drag has entered its "above everything" state, so we can
  // dim the in-place window representation to avoid the illusion of two copies.
  const [swapLifting, setSwapLifting] = useState(false);

  // Resolve current rendered rect from state (without live overrides).
  const rect = useMemo(() => {
    if (state.maximized && state.floatingRect) {
      return state.floatingRect;
    }
    return slotRects[state.homeSlotId];
  }, [state.maximized, state.floatingRect, state.homeSlotId, slotRects]);

  const posRef = useRef({ x: rect.x, y: rect.y });
  const sizeRef = useRef({ w: rect.w, h: rect.h });
  posRef.current = { x: rect.x, y: rect.y };
  sizeRef.current = { w: rect.w, h: rect.h };

  const pendingSnapRef = useRef<SnapRegion | null>(null);

  const getPosition = useCallback(() => posRef.current, []);
  const getSize = useCallback(() => sizeRef.current, []);

  // ===== Free drag (maximized only) =====
  const handleDragMove = useCallback(
    (x: number, y: number) => {
      setLivePos(null);
      const region = pendingSnapRef.current;
      if (region !== null && !disabled) {
        snapWindow(id, region);
      } else {
        move(id, x, y);
      }
    },
    [disabled, id, move, snapWindow],
  );

  const handleLiveDrag = useCallback((x: number, y: number) => {
    setLivePos({ x, y });
  }, []);

  const handlePointerMoveDuringDrag = useCallback(
    (clientX: number, clientY: number) => {
      if (disabled) {
        pendingSnapRef.current = null;
        return;
      }
      const region = detectSnapRegion(
        clientX,
        clientY,
        window.innerWidth,
        window.innerHeight,
      );
      pendingSnapRef.current = region;
      setActiveSnap(region);
    },
    [disabled, setActiveSnap],
  );

  const handleDragEnd = useCallback(() => {
    pendingSnapRef.current = null;
    setActiveSnap(null);
  }, [setActiveSnap]);

  const { handleRef: dragRef } = useDraggable<HTMLDivElement>({
    onMove: handleDragMove,
    onDrag: handleLiveDrag,
    onPointerMove: handlePointerMoveDuringDrag,
    onDragEnd: handleDragEnd,
    getPosition,
    // Free drag is only valid when floating.
    disabled: disabled || !state.maximized,
  });

  // ===== Resize (maximized only) =====
  const handleResize = useCallback(
    (w: number, h: number) => {
      setLiveSize(null);
      resize(id, w, h);
    },
    [id, resize],
  );

  const handleLiveResize = useCallback((w: number, h: number) => {
    setLiveSize({ w, h });
  }, []);

  const { handleRef: resizeRef } = useResizable<HTMLDivElement>({
    onResize: handleResize,
    onResizing: handleLiveResize,
    getSize,
    disabled: disabled || !state.maximized,
    minW: 180,
    minH: 80,
  });

  // ===== Swap drag (minimized only) =====
  const resolveHoveredSlot = useCallback(
    (clientX: number, clientY: number): SlotId | null => {
      return slotAtPoint(clientX, clientY, slotRects);
    },
    [slotRects],
  );

  const handleSwapStart = useCallback(() => {
    setSwapLifting(true);
    focus(id);
    if (onSwapStart) onSwapStart(id);
  }, [focus, id, onSwapStart]);

  const handleSwapMove = useCallback(
    (clientX: number, clientY: number) => {
      if (onSwapMove) onSwapMove(clientX, clientY);
    },
    [onSwapMove],
  );

  const handleSwapCommit = useCallback(
    (slot: SlotId | null) => {
      setSwapLifting(false);
      if (onSwapCommit) onSwapCommit(id, slot);
    },
    [id, onSwapCommit],
  );

  const handleSwapCancel = useCallback(() => {
    setSwapLifting(false);
    if (onSwapCancel) onSwapCancel();
  }, [onSwapCancel]);

  const { handleRef: swapRef } = useSwapDrag<HTMLDivElement>({
    enabled: !disabled && !state.maximized,
    onSwapStart: handleSwapStart,
    onSwapMove: handleSwapMove,
    onSwapCommit: handleSwapCommit,
    onSwapCancel: handleSwapCancel,
    resolveHoveredSlot,
  });

  // The header hosts either the free-drag ref (maximized) or the swap-drag ref
  // (minimized). Using a single callback ref keeps both hooks isolated.
  const headerRef = useCallback(
    (el: HTMLDivElement | null) => {
      dragRef.current = el;
      swapRef.current = el;
    },
    [dragRef, swapRef],
  );

  // ===== Focus-on-pointerdown =====
  const onPointerDownCapture = useCallback(
    (_e: ReactPointerEvent<HTMLDivElement>): void => {
      if (disabled) return;
      if (focusedId !== id) focus(id);
    },
    [disabled, focus, focusedId, id],
  );

  // ===== Double-click on header toggles maximize =====
  const lastClickRef = useRef(0);
  const onHeaderClick = useCallback(() => {
    if (disabled) return;
    const now = performance.now();
    if (now - lastClickRef.current < DOUBLE_CLICK_MS) {
      toggleMaximize(id);
      lastClickRef.current = 0;
    } else {
      lastClickRef.current = now;
    }
  }, [disabled, id, toggleMaximize]);

  // ===== Header buttons =====
  const onMaxMinBtn = useCallback(() => {
    if (disabled) return;
    if (state.maximized) minimize(id);
    else maximize(id);
  }, [disabled, id, maximize, minimize, state.maximized]);

  const onResetBtn = useCallback(
    (e: ReactMouseEvent<HTMLButtonElement>): void => {
      e.stopPropagation();
      resetWindow(id);
    },
    [id, resetWindow],
  );

  const isFocused = focusedId === id;
  const mode: PanelMode = state.maximized ? 'expanded' : 'compact';

  // Resolve rendered geometry — live overrides only apply during free drag/resize.
  const style = useMemo<CSSProperties>(() => {
    const x = livePos ? livePos.x : rect.x;
    const y = livePos ? livePos.y : rect.y;
    const w = liveSize ? liveSize.w : rect.w;
    const h = liveSize ? liveSize.h : rect.h;
    return {
      left: x,
      top: y,
      width: w,
      height: h,
      zIndex: state.zIndex,
      // While the swap-drag lifts the window, the SwapOverlay renders the
      // floating drag preview instead — hide the docked representation.
      opacity: swapLifting ? 0 : undefined,
      pointerEvents: swapLifting ? 'none' : undefined,
    };
  }, [
    livePos,
    liveSize,
    rect.x,
    rect.y,
    rect.w,
    rect.h,
    state.zIndex,
    swapLifting,
  ]);

  // Hidden windows do not render at all — no DOM, no pointer-events.
  if (!state.visible) return <></>;

  const isSettling = settlingIds.has(id);
  const rootClasses = [
    'window',
    `window--${mode}`,
    state.maximized ? 'window--floating' : 'window--docked',
    isFocused ? 'window--focused' : 'window--unfocused',
    disabled ? 'window--idle' : '',
    isSettling ? 'window--settling' : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div
      className={rootClasses}
      style={style}
      role="dialog"
      aria-label={title}
      onPointerDownCapture={onPointerDownCapture}
    >
      <div
        ref={headerRef}
        className="window-header"
        onClick={onHeaderClick}
      >
        {icon !== undefined && <span className="window-header-icon">{icon}</span>}
        <span className="window-header-title" title={title}>
          {title}
        </span>
        <span className="window-header-spacer" />
        <span className="window-header-buttons" data-no-drag>
          <button
            type="button"
            className="window-header-btn window-header-btn--reset"
            onClick={onResetBtn}
            aria-label="Reset window position"
            title="Reset position"
          >
            <svg
              width="12"
              height="12"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.75"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden
              focusable="false"
            >
              <path d="M3 12a9 9 0 1 0 3-6.7" />
              <polyline points="3 3 3 8 8 8" />
            </svg>
          </button>
          <button
            type="button"
            className="window-header-btn"
            onClick={onMaxMinBtn}
            aria-label={state.maximized ? 'Minimize window' : 'Maximize window'}
            title={state.maximized ? 'Minimize' : 'Maximize'}
          >
            {state.maximized ? '\u2B13' : '\u26F6'}
          </button>
        </span>
      </div>

      <div className="window-body">{children(mode)}</div>

      <div
        ref={resizeRef}
        className="window-resize"
        aria-hidden
        data-no-drag
      />
    </div>
  );
}

export default Window;
