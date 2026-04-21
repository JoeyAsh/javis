import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
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
import { HudPanel } from './primitives/HudPanel';
import { HudIconButton } from './primitives/HudIconButton';
import { useSfx } from '../../hud/SfxContext';
import './hud.css';
import './Window.css';

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

/** Pin icon SVG — toggle between pinned (filled) and unpinned (stroke only). */
function PinIcon({ active }: { active: boolean }): ReactElement {
  return (
    <svg
      width="12"
      height="12"
      viewBox="0 0 24 24"
      fill={active ? 'currentColor' : 'none'}
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      focusable="false"
    >
      <line x1="12" y1="17" x2="12" y2="22" />
      <path d="M5 17h14v-1.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V6h1a2 2 0 0 0 0-4H8a2 2 0 0 0 0 4h1v4.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24Z" />
    </svg>
  );
}

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
  const { playOneShot } = useSfx();

  // Pinned state: when pinned the window stays visible regardless of idle mode.
  const [pinned, setPinned] = useState(false);

  // Live-drag position / size (only used while maximized & actively dragging).
  const [livePos, setLivePos] = useState<{ x: number; y: number } | null>(null);
  const [liveSize, setLiveSize] = useState<{ w: number; h: number } | null>(null);
  // True while a swap-drag has entered its "above everything" state, so we can
  // dim the in-place window representation to avoid the illusion of two copies.
  const [swapLifting, setSwapLifting] = useState(false);

  // Track whether the window is expanded (maximized) for SFX purposes.
  const prevMaximizedRef = useRef(state.maximized);

  // Fire expand/collapse SFX when maximized state changes (pointer-initiated).
  const lastPointerEventRef = useRef<number>(0);
  const SFX_GUARD_MS = 100; // Only fire if a pointer event happened recently.

  useEffect(() => {
    const wasMaximized = prevMaximizedRef.current;
    const isMaximized = state.maximized;
    prevMaximizedRef.current = isMaximized;

    if (wasMaximized === isMaximized) return;

    const now = performance.now();
    if (now - lastPointerEventRef.current < SFX_GUARD_MS) {
      playOneShot(isMaximized ? 'expand' : 'collapse');
    }
  }, [state.maximized, playOneShot]);

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

  const handleDragStartSfx = useCallback(() => {
    playOneShot('drag_start');
  }, [playOneShot]);

  const handleDragStopSfx = useCallback(() => {
    playOneShot('drag_end');
  }, [playOneShot]);

  const { handleRef: dragRef } = useDraggable<HTMLDivElement>({
    onMove: handleDragMove,
    onDrag: handleLiveDrag,
    onPointerMove: handlePointerMoveDuringDrag,
    onDragEnd: handleDragEnd,
    onDragStart: handleDragStartSfx,
    onDragStop: handleDragStopSfx,
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

  const handleResizeEndSfx = useCallback(() => {
    playOneShot('resize');
  }, [playOneShot]);

  const { handleRef: resizeRef } = useResizable<HTMLDivElement>({
    onResize: handleResize,
    onResizing: handleLiveResize,
    onResizeEnd: handleResizeEndSfx,
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
      lastPointerEventRef.current = performance.now();
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
      lastPointerEventRef.current = performance.now();
      toggleMaximize(id);
      lastClickRef.current = 0;
    } else {
      lastClickRef.current = now;
    }
  }, [disabled, id, toggleMaximize]);

  // ===== Header buttons =====
  const onMaxMinBtn = useCallback(
    (e: ReactMouseEvent<HTMLButtonElement>) => {
      if (disabled) return;
      e.stopPropagation();
      lastPointerEventRef.current = performance.now();
      if (state.maximized) minimize(id);
      else maximize(id);
    },
    [disabled, id, maximize, minimize, state.maximized],
  );

  const onResetBtn = useCallback(
    (e: ReactMouseEvent<HTMLButtonElement>): void => {
      e.stopPropagation();
      resetWindow(id);
    },
    [id, resetWindow],
  );

  // ===== Pin button =====
  const onPinBtn = useCallback(
    (e: ReactMouseEvent<HTMLButtonElement>) => {
      if (disabled) return;
      e.stopPropagation();
      lastPointerEventRef.current = performance.now();
      setPinned((prev) => {
        const next = !prev;
        // SFX guard: pointer event was recent (button click itself counts).
        playOneShot(next ? 'pin' : 'unpin');
        return next;
      });
    },
    [disabled, playOneShot],
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

  // Apply idle only when not pinned.
  const isIdle = disabled && !pinned;

  const rootClasses = [
    'window',
    `window--${mode}`,
    state.maximized ? 'window--floating' : 'window--docked',
    isFocused ? 'window--focused' : 'window--unfocused',
    isIdle ? 'window--idle' : '',
    isSettling ? 'window--settling' : '',
    'hud-win-in',
  ]
    .filter(Boolean)
    .join(' ');

  // Header actions: pin + reset + max/min buttons in the header's right slot.
  const headerActions = (
    <span className="window-header-buttons" data-no-drag>
      {/* Pin button */}
      <HudIconButton
        aria-label={pinned ? 'Unpin window' : 'Pin window'}
        active={pinned}
        onClick={onPinBtn}
        disabled={disabled && !pinned}
      >
        <PinIcon active={pinned} />
      </HudIconButton>
      {/* Reset position */}
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
      {/* Maximize / minimize */}
      <button
        type="button"
        className="window-header-btn"
        onClick={onMaxMinBtn}
        aria-label={state.maximized ? 'Minimize window' : 'Maximize window'}
        title={state.maximized ? 'Minimize' : 'Maximize'}
      >
        {state.maximized ? '⬓' : '⛶'}
      </button>
    </span>
  );

  return (
    <div
      className={rootClasses}
      style={style}
      role="dialog"
      aria-label={title}
      onPointerDownCapture={onPointerDownCapture}
    >
      <HudPanel
        focused={isFocused}
        icon={icon}
        title={title}
        actions={headerActions}
        headerRef={headerRef}
        onHeaderClick={onHeaderClick}
        style={{ height: '100%', display: 'flex', flexDirection: 'column' } as CSSProperties}
      >
        <div className="window-body">{children(mode)}</div>
      </HudPanel>

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
