import { useCallback, useEffect, useRef, useState, type ReactElement } from 'react';
import { Window } from '../../window/Window';
import type { WindowState } from '../../window/Window';
import { SnapOverlay } from '../../window/SnapOverlay';
import { SwapOverlay } from '../../window/SwapOverlay';
import { computeAllSlots, TOP_BAR_HEIGHT } from '../../window/slotGrid';
import type { SlotId, SlotRect } from '../../window/slotGrid';
import type { ResizeDir } from '../../window/hooks/useResizable';
import type {
    ManagedWindow,
    ExpandedRect,
    WindowManagerProps,
    PanelMode,
    PanelContentRenderProps,
    ActiveDrag,
    FreeDrag,
    ViewportSize,
} from './WindowManager.types';

// Re-export so consumers can import from this module.
export type { PanelMode, PanelContentRenderProps, ManagedWindow, ExpandedRect };

function getViewport(): ViewportSize {
    return {
        w: typeof window !== 'undefined' ? window.innerWidth : 1280,
        h: typeof window !== 'undefined' ? window.innerHeight : 900,
    };
}

/** Per-window local state tracked internally by WindowManager. */
type WindowLocalState = 'idle' | 'resizing';

/**
 * Compute a new SlotRect after a resize gesture.
 */
function applyResize(
    start: SlotRect,
    dir: ResizeDir,
    dx: number,
    dy: number,
    minW = 120,
    minH = 80,
): SlotRect {
    let { x, y, w, h } = start;

    if (dir.includes('e')) {
        w = Math.max(minW, start.w + dx);
    }
    if (dir.includes('s')) {
        h = Math.max(minH, start.h + dy);
    }
    if (dir.includes('w')) {
        const newW = Math.max(minW, start.w - dx);
        x = start.x + (start.w - newW);
        w = newW;
    }
    if (dir.includes('n')) {
        const newH = Math.max(minH, start.h - dy);
        y = start.y + (start.h - newH);
        h = newH;
    }

    return { x, y, w, h };
}

/** Minimum dimensions for clamping expanded rects. */
const MIN_EXPANDED_W = 180;
const MIN_EXPANDED_H = 80;

/** Clamp an expanded rect so it stays within the visible workspace. */
function clampExpandedRect(rect: ExpandedRect, W: number, H: number): ExpandedRect {
    const w = Math.max(MIN_EXPANDED_W, Math.min(rect.w, W));
    const h = Math.max(MIN_EXPANDED_H, Math.min(rect.h, H - TOP_BAR_HEIGHT));
    const x = Math.max(0, Math.min(rect.x, Math.max(0, W - w)));
    const y = Math.max(TOP_BAR_HEIGHT, Math.min(rect.y, Math.max(TOP_BAR_HEIGHT, H - h)));
    return { x, y, w, h };
}

/**
 * Derive a sensible default floating rect when a window is first expanded.
 * Centers approximately on the slot at ~1.8× width / 1.6× height.
 */
function defaultExpandedRect(slotRect: SlotRect, W: number, H: number): ExpandedRect {
    const cx = slotRect.x + slotRect.w / 2;
    const cy = slotRect.y + slotRect.h / 2;
    const w = Math.floor(slotRect.w * 1.8);
    const h = Math.floor(slotRect.h * 1.6);
    const x = Math.floor(cx - w / 2);
    const y = Math.floor(cy - h / 2);
    return clampExpandedRect({ x, y, w, h }, W, H);
}

// ── WindowManager ─────────────────────────────────────────────────────────────

/**
 * WindowManager — controlled composition that renders N windows at slot-derived
 * positions (compact mode) or at free-floating positions (expanded mode).
 */
export function WindowManager({
    windows,
    assignments,
    onAssignmentsChange,
    homeAssignments,
    focusedId = null,
    onFocusChange,
    modes: modesProp,
    onModesChange,
    expandedRects: expandedRectsProp,
    className,
}: WindowManagerProps): ReactElement {
    const [viewport, setViewport] = useState<ViewportSize>(getViewport);

    // Per-window local state (resizing/idle).
    const [windowStates, setWindowStates] = useState<Record<string, WindowLocalState>>({});

    // Custom per-window rect overrides from resize gestures (compact mode).
    const [customRects, setCustomRects] = useState<Record<string, SlotRect>>({});

    // Starting rect captured at resize-start for computing deltas live.
    const resizeStartRectRef = useRef<Record<string, SlotRect>>({});

    // ── Mode state (uncontrolled unless `modes` prop is provided) ──────────────
    const [internalModes, setInternalModes] = useState<Record<string, PanelMode>>({});
    const isModesControlled = modesProp !== undefined;
    const modes: Record<string, PanelMode> = isModesControlled ? modesProp : internalModes;

    // ── Expanded rect state (uncontrolled unless `expandedRects` prop provided) ─
    const [internalExpandedRects, setInternalExpandedRects] = useState<
        Record<string, ExpandedRect>
    >({});
    const isExpandedControlled = expandedRectsProp !== undefined;
    const expandedRects: Record<string, ExpandedRect> = isExpandedControlled
        ? expandedRectsProp
        : internalExpandedRects;

    // Recompute on resize.
    useEffect(() => {
        const onResize = (): void => {
            const vp = getViewport();
            setViewport(vp);
            // Clamp all expanded rects to new viewport.
            if (!isExpandedControlled) {
                setInternalExpandedRects((prev) => {
                    const next = { ...prev };
                    let changed = false;
                    for (const id of Object.keys(next)) {
                        const clamped = clampExpandedRect(next[id], vp.w, vp.h);
                        if (
                            clamped.x !== next[id].x ||
                            clamped.y !== next[id].y ||
                            clamped.w !== next[id].w ||
                            clamped.h !== next[id].h
                        ) {
                            next[id] = clamped;
                            changed = true;
                        }
                    }
                    return changed ? next : prev;
                });
            }
        };
        window.addEventListener('resize', onResize);
        return () => {
            window.removeEventListener('resize', onResize);
        };
    }, [isExpandedControlled]);

    const slotRects = computeAllSlots(viewport.w, viewport.h);

    // ── Compact slot-drag state ────────────────────────────────────────────────
    const [activeDrag, setActiveDrag] = useState<ActiveDrag | null>(null);
    const [snapTarget, setSnapTarget] = useState<SlotId | null>(null);
    const [swapTarget, setSwapTarget] = useState<string | null>(null);

    // ── Expanded free-drag state ───────────────────────────────────────────────
    const [freeDrag, setFreeDrag] = useState<FreeDrag | null>(null);
    // Live position during free drag (avoids updating expandedRects on every move).
    const [freeDragPos, setFreeDragPos] = useState<{ x: number; y: number } | null>(null);

    // ── Expanded resize state ──────────────────────────────────────────────────
    const expandedResizeStartRef = useRef<Record<string, ExpandedRect>>({});

    // Keep assignments in a ref so event handlers never close over stale values.
    const assignmentsRef = useRef(assignments);
    assignmentsRef.current = assignments;

    const modesRef = useRef(modes);
    modesRef.current = modes;

    const expandedRectsRef = useRef(expandedRects);
    expandedRectsRef.current = expandedRects;

    // Home assignments — captured once on mount (or taken from prop).
    const homeRef = useRef<Record<string, SlotId>>(homeAssignments ?? assignments);

    // ── Mode helpers ───────────────────────────────────────────────────────────

    const setMode = useCallback(
        (id: string, next: PanelMode): void => {
            if (isModesControlled) {
                if (onModesChange) onModesChange({ ...modesRef.current, [id]: next });
            } else {
                setInternalModes((prev) => {
                    const updated = { ...prev, [id]: next };
                    if (onModesChange) onModesChange(updated);
                    return updated;
                });
            }
        },
        [isModesControlled, onModesChange],
    );

    const setExpandedRect = useCallback(
        (id: string, rect: ExpandedRect): void => {
            if (!isExpandedControlled) {
                setInternalExpandedRects((prev) => ({ ...prev, [id]: rect }));
            }
        },
        [isExpandedControlled],
    );

    const clearExpandedRect = useCallback(
        (id: string): void => {
            if (!isExpandedControlled) {
                setInternalExpandedRects((prev) => {
                    const copy = { ...prev };
                    delete copy[id];
                    return copy;
                });
            }
        },
        [isExpandedControlled],
    );

    // ── Mode toggle (from button or double-click) ──────────────────────────────

    const handleModeToggle = useCallback(
        (id: string): void => {
            const current = modesRef.current[id] ?? 'compact';
            const next: PanelMode = current === 'compact' ? 'expanded' : 'compact';
            if (next === 'expanded') {
                // Compute default expanded rect from slot.
                const slotId = assignmentsRef.current[id] as SlotId | undefined;
                if (slotId !== undefined) {
                    const rects = computeAllSlots(
                        typeof window !== 'undefined' ? window.innerWidth : 1280,
                        typeof window !== 'undefined' ? window.innerHeight : 900,
                    );
                    const existing = expandedRectsRef.current[id];
                    const rect = existing
                        ? clampExpandedRect(
                              existing,
                              typeof window !== 'undefined' ? window.innerWidth : 1280,
                              typeof window !== 'undefined' ? window.innerHeight : 900,
                          )
                        : defaultExpandedRect(
                              rects[slotId],
                              typeof window !== 'undefined' ? window.innerWidth : 1280,
                              typeof window !== 'undefined' ? window.innerHeight : 900,
                          );
                    setExpandedRect(id, rect);
                }
            }
            setMode(id, next);
            // Focus the toggled window.
            if (onFocusChange) onFocusChange(id);
        },
        [setMode, setExpandedRect, onFocusChange],
    );

    // ── Focus ─────────────────────────────────────────────────────────────────

    const handleFocus = useCallback(
        (id: string): void => {
            if (onFocusChange) onFocusChange(id);
        },
        [onFocusChange],
    );

    // ── Compact drag: slot-swap ────────────────────────────────────────────────

    const windowAtSlot = useCallback((slotId: SlotId, excludeId: string): string | null => {
        for (const [wId, sId] of Object.entries(assignmentsRef.current)) {
            if (sId === slotId && wId !== excludeId) return wId;
        }
        return null;
    }, []);

    const handleDragStart = useCallback((id: string): void => {
        const current = modesRef.current[id] ?? 'compact';
        if (current === 'expanded') return; // expanded drag handled separately
        const origin = assignmentsRef.current[id] as SlotId | undefined;
        if (origin === undefined) return;
        setActiveDrag({ windowId: id, originSlot: origin });
        setSnapTarget(null);
        setSwapTarget(null);
    }, []);

    const handleDragMove = useCallback(
        (id: string, _dx: number, _dy: number, e: PointerEvent): void => {
            const current = modesRef.current[id] ?? 'compact';
            if (current === 'expanded') return;
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
            setSnapTarget(hovered);
            const swap = hovered !== null ? windowAtSlot(hovered, id) : null;
            setSwapTarget(swap);
        },
        [windowAtSlot],
    );

    const handleDragEnd = useCallback(
        (id: string, e: PointerEvent): void => {
            const current = modesRef.current[id] ?? 'compact';
            if (current === 'expanded') return;

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

            const current2 = assignmentsRef.current;
            const originSlot = current2[id] as SlotId | undefined;

            if (hovered !== null && originSlot !== undefined) {
                const occupant = windowAtSlot(hovered, id);
                if (occupant !== null) {
                    const next: Record<string, SlotId> = { ...current2 };
                    next[id] = hovered;
                    next[occupant] = originSlot;
                    onAssignmentsChange(next);
                } else if (hovered !== originSlot) {
                    const next: Record<string, SlotId> = { ...current2 };
                    next[id] = hovered;
                    onAssignmentsChange(next);
                }
            }

            setActiveDrag(null);
            setSnapTarget(null);
            setSwapTarget(null);
        },
        [windowAtSlot, onAssignmentsChange],
    );

    // ── Expanded free-drag ─────────────────────────────────────────────────────

    const handleExpandedDragStart = useCallback(
        (id: string, e: React.PointerEvent): void => {
            const current = modesRef.current[id] ?? 'compact';
            if (current !== 'expanded') return;
            const rect = expandedRectsRef.current[id];
            if (!rect) return;
            setFreeDrag({
                windowId: id,
                startX: e.clientX,
                startY: e.clientY,
                originX: rect.x,
                originY: rect.y,
            });
            setFreeDragPos({ x: rect.x, y: rect.y });
            if (onFocusChange) onFocusChange(id);
        },
        [onFocusChange],
    );

    const handleExpandedDragMove = useCallback(
        (id: string, dx: number, dy: number, _e: PointerEvent): void => {
            const current = modesRef.current[id] ?? 'compact';
            if (current !== 'expanded') return;
            setFreeDrag((prev) => {
                if (!prev || prev.windowId !== id) return prev;
                const vp = getViewport();
                const rect = expandedRectsRef.current[id];
                const w = rect ? rect.w : MIN_EXPANDED_W;
                const h = rect ? rect.h : MIN_EXPANDED_H;
                const rawX = prev.originX + dx;
                const rawY = prev.originY + dy;
                const x = Math.max(0, Math.min(rawX, Math.max(0, vp.w - w)));
                const y = Math.max(
                    TOP_BAR_HEIGHT,
                    Math.min(rawY, Math.max(TOP_BAR_HEIGHT, vp.h - h)),
                );
                setFreeDragPos({ x, y });
                return prev;
            });
        },
        [],
    );

    const handleExpandedDragEnd = useCallback(
        (id: string, _e: PointerEvent): void => {
            const current = modesRef.current[id] ?? 'compact';
            if (current !== 'expanded') return;
            setFreeDrag((prev) => {
                if (!prev || prev.windowId !== id) return prev;
                // Commit final position.
                setFreeDragPos((pos) => {
                    if (pos) {
                        const rect = expandedRectsRef.current[id];
                        if (rect) {
                            setExpandedRect(id, { ...rect, x: pos.x, y: pos.y });
                        }
                    }
                    return null;
                });
                return null;
            });
        },
        [setExpandedRect],
    );

    // ── Compact resize handlers ────────────────────────────────────────────────

    const handleResizeStart = useCallback(
        (id: string, _dir: ResizeDir): void => {
            const mode = modesRef.current[id] ?? 'compact';
            const slotId = assignmentsRef.current[id] as SlotId | undefined;
            if (slotId === undefined) return;

            if (mode === 'expanded') {
                // Expanded resize — capture current expanded rect.
                const rect = expandedRectsRef.current[id];
                if (rect) expandedResizeStartRef.current[id] = rect;
            } else {
                // Compact resize.
                const currentCustom = customRects[id];
                const baseRect = currentCustom ?? slotRects[slotId];
                resizeStartRectRef.current[id] = baseRect;
            }

            setWindowStates((prev) => ({ ...prev, [id]: 'resizing' }));
        },
        // eslint-disable-next-line react-hooks/exhaustive-deps
        [customRects, slotRects],
    );

    const handleResizeMove = useCallback(
        (id: string, dir: ResizeDir, dx: number, dy: number): void => {
            const mode = modesRef.current[id] ?? 'compact';
            if (mode === 'expanded') {
                const startRect = expandedResizeStartRef.current[id];
                if (!startRect) return;
                const newRect = applyResize(startRect, dir, dx, dy, MIN_EXPANDED_W, MIN_EXPANDED_H);
                setExpandedRect(id, newRect);
            } else {
                const startRect = resizeStartRectRef.current[id];
                if (startRect === undefined) return;
                const newRect = applyResize(startRect, dir, dx, dy);
                setCustomRects((prev) => ({ ...prev, [id]: newRect }));
            }
        },
        [setExpandedRect],
    );

    const handleResizeEnd = useCallback((id: string): void => {
        setWindowStates((prev) => ({ ...prev, [id]: 'idle' }));
    }, []);

    // ── Reset ─────────────────────────────────────────────────────────────────

    const handleReset = useCallback(
        (id: string): void => {
            // Clear custom compact rect.
            setCustomRects((prev) => {
                const copy = { ...prev };
                delete copy[id];
                return copy;
            });
            // Clear expanded rect.
            clearExpandedRect(id);
            // Reset mode to compact.
            setMode(id, 'compact');
            // Reset to home slot.
            const homeSlot = homeRef.current[id] as SlotId | undefined;
            if (homeSlot !== undefined) {
                onAssignmentsChange({ ...assignmentsRef.current, [id]: homeSlot });
            }
            setWindowStates((prev) => ({ ...prev, [id]: 'idle' }));
        },
        [onAssignmentsChange, clearExpandedRect, setMode],
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

    // Compute ghostRect for SwapOverlay.
    const swapGhostRect: SlotRect | null =
        swapTarget !== null ? (slotRects[assignments[swapTarget] as SlotId] ?? null) : null;

    return (
        <div className={rootCls}>
            {windows.map((win) => {
                const slotId = assignments[win.id] as SlotId | undefined;
                if (slotId === undefined) return null;

                const mode: PanelMode = modes[win.id] ?? 'compact';
                const baseRect = slotRects[slotId];
                const localState = windowStates[win.id] ?? 'idle';
                const isCompactDragging =
                    activeDrag !== null && activeDrag.windowId === win.id && mode === 'compact';
                const isExpandedDragging =
                    freeDrag !== null && freeDrag.windowId === win.id && mode === 'expanded';
                const isFocused = focusedId === win.id;

                // Resolve position:
                // - expanded → expandedRects[id] (with live drag override)
                // - compact → slot rect (with custom resize override)
                let position: { x: number; y: number; w: number; h: number };

                if (mode === 'expanded') {
                    const expRect = expandedRects[win.id];
                    if (expRect) {
                        const liveX =
                            isExpandedDragging && freeDragPos ? freeDragPos.x : expRect.x;
                        const liveY =
                            isExpandedDragging && freeDragPos ? freeDragPos.y : expRect.y;
                        position = { x: liveX, y: liveY, w: expRect.w, h: expRect.h };
                    } else {
                        // Expanded rect not yet computed — fall back to slot rect.
                        position = baseRect;
                    }
                } else {
                    position = customRects[win.id] ?? baseRect;
                }

                // Resolve visual window state.
                let winState: WindowState = 'idle';
                if (localState === 'resizing') {
                    winState = 'resizing';
                } else if (isExpandedDragging) {
                    winState = 'dragging';
                } else if (isCompactDragging) {
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

                // In compact mode: drag fires compact drag handlers.
                // In expanded mode: drag fires expanded free-drag handlers.
                // Resize only works in expanded mode (CSS hides handles in compact).
                const isDraggable = true;
                const isResizable = mode === 'expanded';

                return (
                    <Window
                        key={win.id}
                        id={win.id}
                        title={win.title}
                        ix={win.ix}
                        badge={win.badge}
                        position={position}
                        state={winState}
                        mode={mode}
                        focused={isFocused}
                        onFocus={handleFocus}
                        onDragStart={
                            mode === 'expanded' ? handleExpandedDragStart : handleDragStart
                        }
                        onDragMove={
                            mode === 'expanded' ? handleExpandedDragMove : handleDragMove
                        }
                        onDragEnd={mode === 'expanded' ? handleExpandedDragEnd : handleDragEnd}
                        onResizeStart={handleResizeStart}
                        onResizeMove={handleResizeMove}
                        onResizeEnd={handleResizeEnd}
                        onReset={handleReset}
                        onModeToggle={handleModeToggle}
                        draggable={isDraggable}
                        resizable={isResizable}
                        itemRenderer={win.itemRenderer}
                    />
                );
            })}

            {/* SnapOverlay and SwapOverlay only active during compact drag */}
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
