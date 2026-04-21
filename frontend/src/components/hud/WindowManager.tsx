import {
    createContext,
    useCallback,
    useContext,
    useEffect,
    useMemo,
    useRef,
    useState,
} from 'react';
import type { ReactElement, ReactNode } from 'react';
import type { PanelId } from '../../types';
import { computeSlot, DEFAULT_ASSIGNMENTS, SLOT_IDS, TOP_BAR_HEIGHT } from './SlotGrid';
import type { SlotId, SlotRect } from './SlotGrid';

// Re-export the TOP_BAR_HEIGHT for consumers that rely on it from WindowManager.
export { TOP_BAR_HEIGHT };
export type { SlotId, SlotRect };

/** Rect shape used by the Win11-snap helpers. */
export interface SnapRect {
    x: number;
    y: number;
    w: number;
    h: number;
}

/** Floating-window geometry, only meaningful while `maximized === true`. */
export interface FloatingRect {
    x: number;
    y: number;
    w: number;
    h: number;
}

/**
 * Per-window record.
 *
 * Semantics:
 * - When `maximized === false`, the window is docked in its home slot. Geometry
 *   is derived from `homeSlotId` and the current viewport. `floatingRect` is
 *   remembered across toggles.
 * - When `maximized === true`, the window floats at `floatingRect` and supports
 *   drag / resize / Win11 snap.
 */
export interface WindowState {
    id: PanelId;
    homeSlotId: SlotId;
    maximized: boolean;
    floatingRect: FloatingRect | null;
    zIndex: number;
    visible: boolean;
}

export type WindowMap = Record<PanelId, WindowState>;

/** Windows-11-style snap regions. */
export type SnapRegion =
    | 'LEFT_HALF'
    | 'RIGHT_HALF'
    | 'MAXIMIZE'
    | 'BOTTOM_LEFT_QUARTER'
    | 'BOTTOM_RIGHT_QUARTER';

/**
 * Pure helper to resolve a snap region into its target rect for a given
 * viewport. Exported so overlay rendering can re-use identical math.
 */
export function computeSnapRect(
    region: SnapRegion,
    viewportW: number,
    viewportH: number,
): SnapRect {
    const topBar = TOP_BAR_HEIGHT;
    const workspaceH = viewportH - topBar;
    const halfW = Math.floor(viewportW / 2);
    const halfH = Math.floor(workspaceH / 2);
    switch (region) {
        case 'MAXIMIZE':
            return { x: 0, y: topBar, w: viewportW, h: workspaceH };
        case 'LEFT_HALF':
            return { x: 0, y: topBar, w: halfW, h: workspaceH };
        case 'RIGHT_HALF':
            return { x: halfW, y: topBar, w: viewportW - halfW, h: workspaceH };
        case 'BOTTOM_LEFT_QUARTER':
            return { x: 0, y: topBar + halfH, w: halfW, h: workspaceH - halfH };
        case 'BOTTOM_RIGHT_QUARTER':
            return {
                x: halfW,
                y: topBar + halfH,
                w: viewportW - halfW,
                h: workspaceH - halfH,
            };
        default: {
            const _exhaustive: never = region;
            void _exhaustive;
            return { x: 0, y: topBar, w: viewportW, h: workspaceH };
        }
    }
}

/**
 * Classify a viewport pointer position into a SnapRegion, or null if none.
 * Precedence: MAXIMIZE -> corners -> halves.
 */
export function detectSnapRegion(
    pointerX: number,
    pointerY: number,
    viewportW: number,
    viewportH: number,
): SnapRegion | null {
    const topBar = TOP_BAR_HEIGHT;
    if (pointerY <= topBar + 6) return 'MAXIMIZE';
    if (pointerX <= 40 && pointerY >= viewportH - 40) return 'BOTTOM_LEFT_QUARTER';
    if (pointerX >= viewportW - 40 && pointerY >= viewportH - 40) {
        return 'BOTTOM_RIGHT_QUARTER';
    }
    if (pointerX <= 18 && pointerY > topBar + 40 && pointerY < viewportH - 40) {
        return 'LEFT_HALF';
    }
    if (pointerX >= viewportW - 18 && pointerY > topBar + 40 && pointerY < viewportH - 40) {
        return 'RIGHT_HALF';
    }
    return null;
}

interface WindowManagerValue {
    windows: WindowMap;
    focusedId: PanelId | null;
    activeSnap: SnapRegion | null;
    settlingIds: ReadonlySet<PanelId>;
    slotRects: Record<SlotId, SlotRect>;

    focus: (id: PanelId) => void;
    clearFocus: () => void;

    maximize: (id: PanelId) => void;
    minimize: (id: PanelId) => void;
    toggleMaximize: (id: PanelId) => void;

    move: (id: PanelId, x: number, y: number) => void;
    resize: (id: PanelId, w: number, h: number) => void;
    setActiveSnap: (region: SnapRegion | null) => void;
    snapWindow: (id: PanelId, region: SnapRegion) => void;

    swapSlots: (a: PanelId, b: PanelId) => void;

    resetWindow: (id: PanelId) => void;
    resetAll: () => void;
}

const STORAGE_KEY_OLD = 'jarvis-hud-layout-v1';
const STORAGE_KEY = 'jarvis-hud-windows-v1';
const PERSIST_DEBOUNCE_MS = 200;
const SETTLING_DURATION_MS = 320;

const PANEL_ORDER: ReadonlyArray<PanelId> = [
    'agenda',
    'mail',
    'notifications',
    'transcript',
    'nowplaying',
    'lights',
    'system',
    'dev',
    'selffix',
    'gitlab',
    'log',
];

const INITIAL_Z_BASE = 10;
const Z_STEP = 10;

const WindowManagerContext = createContext<WindowManagerValue | null>(null);

export interface WindowManagerProviderProps {
    children: ReactNode;
}

function migrateOldStorage(): void {
    try {
        if (localStorage.getItem(STORAGE_KEY_OLD) !== null) {
            localStorage.removeItem(STORAGE_KEY_OLD);
        }
    } catch {
        // ignore storage errors
    }
}

/**
 * Build the initial WindowMap from `DEFAULT_ASSIGNMENTS`. Everything starts
 * minimized (docked into its home slot) with no floatingRect cached.
 */
function computeDefaults(): WindowMap {
    const out = {} as WindowMap;
    PANEL_ORDER.forEach((id, idx) => {
        out[id] = {
            id,
            homeSlotId: DEFAULT_ASSIGNMENTS[id],
            maximized: false,
            floatingRect: null,
            zIndex: INITIAL_Z_BASE + idx * Z_STEP,
            visible: true,
        };
    });
    return out;
}

/** Compute the full set of slot rects for the current viewport. */
function computeSlotRects(W: number, H: number): Record<SlotId, SlotRect> {
    const out = {} as Record<SlotId, SlotRect>;
    for (const id of SLOT_IDS) {
        out[id] = computeSlot(id, W, H);
    }
    return out;
}

/** Clamp a FloatingRect into the visible workspace (below the top bar). */
function clampFloatingRect(rect: FloatingRect, W: number, H: number): FloatingRect {
    const minW = 180;
    const minH = 80;
    const w = Math.max(minW, Math.min(rect.w, W));
    const h = Math.max(minH, Math.min(rect.h, H - TOP_BAR_HEIGHT));
    const x = Math.max(0, Math.min(rect.x, Math.max(0, W - w)));
    const y = Math.max(TOP_BAR_HEIGHT, Math.min(rect.y, Math.max(TOP_BAR_HEIGHT, H - h)));
    return { x, y, w, h };
}

/** Produce a default floating rect for a freshly-maximized window. */
function defaultFloatingRect(slotRect: SlotRect, W: number, H: number): FloatingRect {
    const cx = slotRect.x + slotRect.w / 2;
    const cy = slotRect.y + slotRect.h / 2;
    const w = Math.floor(slotRect.w * 1.8);
    const h = Math.floor(slotRect.h * 1.6);
    const x = Math.floor(cx - w / 2);
    const y = Math.floor(cy - h / 2);
    return clampFloatingRect({ x, y, w, h }, W, H);
}

/** Structural detection for the new persisted shape. */
interface PersistedWindowShape {
    homeSlotId: SlotId;
    maximized: boolean;
    floatingRect: FloatingRect | null;
    zIndex: number;
    visible: boolean;
}

interface PersistedShape {
    version: 2;
    windows: Partial<Record<PanelId, Partial<PersistedWindowShape>>>;
}

const VALID_SLOT_IDS: ReadonlySet<string> = new Set<SlotId>(SLOT_IDS);

function isSlotId(v: unknown): v is SlotId {
    return typeof v === 'string' && VALID_SLOT_IDS.has(v);
}

function looksLikeNewShape(parsed: unknown): parsed is PersistedShape {
    if (!parsed || typeof parsed !== 'object') return false;
    const maybe = parsed as { windows?: unknown };
    if (!maybe.windows || typeof maybe.windows !== 'object') return false;
    // "entries have `homeSlotId` key" is the heuristic per the design doc.
    for (const key of Object.keys(maybe.windows)) {
        const entry = (maybe.windows as Record<string, unknown>)[key];
        if (
            entry !== null &&
            typeof entry === 'object' &&
            'homeSlotId' in (entry as Record<string, unknown>)
        ) {
            return true;
        }
    }
    return false;
}

function loadPersisted(defaults: WindowMap, W: number, H: number): WindowMap {
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (!raw) return defaults;
        const parsed = JSON.parse(raw) as unknown;
        if (!looksLikeNewShape(parsed)) {
            // Old shape (or unparseable) — discard.
            try {
                localStorage.removeItem(STORAGE_KEY);
            } catch {
                // ignore
            }
            return defaults;
        }
        const merged = { ...defaults } as WindowMap;
        for (const id of PANEL_ORDER) {
            const persisted = parsed.windows[id];
            if (!persisted) continue;
            const base = defaults[id];
            const nextSlot: SlotId = isSlotId(persisted.homeSlotId)
                ? persisted.homeSlotId
                : base.homeSlotId;
            const nextMax =
                typeof persisted.maximized === 'boolean' ? persisted.maximized : base.maximized;
            const rawFloat =
                persisted.floatingRect &&
                typeof persisted.floatingRect === 'object' &&
                typeof persisted.floatingRect.x === 'number' &&
                typeof persisted.floatingRect.y === 'number' &&
                typeof persisted.floatingRect.w === 'number' &&
                typeof persisted.floatingRect.h === 'number'
                    ? clampFloatingRect(persisted.floatingRect, W, H)
                    : null;
            const nextZ = typeof persisted.zIndex === 'number' ? persisted.zIndex : base.zIndex;
            const nextVisible =
                typeof persisted.visible === 'boolean' ? persisted.visible : base.visible;
            merged[id] = {
                id: base.id,
                homeSlotId: nextSlot,
                maximized: nextMax,
                floatingRect: rawFloat,
                zIndex: nextZ,
                visible: nextVisible,
            };
        }
        // Detect duplicate slot assignments — if two panels landed in the same
        // slot (corrupted state), reset to defaults for safety.
        const occupancy: Partial<Record<SlotId, PanelId>> = {};
        for (const id of PANEL_ORDER) {
            const slot = merged[id].homeSlotId;
            if (occupancy[slot] !== undefined) {
                return defaults;
            }
            occupancy[slot] = id;
        }
        return merged;
    } catch {
        return defaults;
    }
}

export function WindowManagerProvider({ children }: WindowManagerProviderProps): ReactElement {
    // Defaults captured at mount. Exposed via ref so resetWindow can restore a
    // single panel to its initial record without touching siblings.
    const defaultsRef = useRef<Map<PanelId, WindowState>>(new Map());

    const [windows, setWindows] = useState<WindowMap>(() => {
        migrateOldStorage();
        const vw = typeof window !== 'undefined' ? window.innerWidth : 1920;
        const vh = typeof window !== 'undefined' ? window.innerHeight : 1080;
        const defaults = computeDefaults();
        const map = new Map<PanelId, WindowState>();
        for (const id of PANEL_ORDER) {
            map.set(id, { ...defaults[id] });
        }
        defaultsRef.current = map;
        return loadPersisted(defaults, vw, vh);
    });

    const [focusedId, setFocusedId] = useState<PanelId | null>(null);
    const [activeSnap, setActiveSnapState] = useState<SnapRegion | null>(null);

    // Slot rects re-computed on viewport resize.
    const [slotRects, setSlotRects] = useState<Record<SlotId, SlotRect>>(() => {
        const vw = typeof window !== 'undefined' ? window.innerWidth : 1920;
        const vh = typeof window !== 'undefined' ? window.innerHeight : 1080;
        return computeSlotRects(vw, vh);
    });

    // Animating-geometry settle set.
    const [settlingIds, setSettlingIds] = useState<ReadonlySet<PanelId>>(() => new Set<PanelId>());
    const settlingTimeoutsRef = useRef<Map<PanelId, number>>(new Map());

    const markSettling = useCallback((ids: ReadonlyArray<PanelId>): void => {
        if (ids.length === 0) return;
        setSettlingIds((prev) => {
            const next = new Set(prev);
            for (const id of ids) next.add(id);
            return next;
        });
        for (const id of ids) {
            const prevTimeout = settlingTimeoutsRef.current.get(id);
            if (prevTimeout !== undefined) {
                window.clearTimeout(prevTimeout);
            }
            const t = window.setTimeout(() => {
                settlingTimeoutsRef.current.delete(id);
                setSettlingIds((prev) => {
                    if (!prev.has(id)) return prev;
                    const next = new Set(prev);
                    next.delete(id);
                    return next;
                });
            }, SETTLING_DURATION_MS);
            settlingTimeoutsRef.current.set(id, t);
        }
    }, []);

    // Debounced persistence.
    const saveTimeoutRef = useRef<number | null>(null);
    useEffect(() => {
        if (saveTimeoutRef.current !== null) {
            window.clearTimeout(saveTimeoutRef.current);
        }
        saveTimeoutRef.current = window.setTimeout(() => {
            try {
                const payload: PersistedShape = {
                    version: 2,
                    windows: {},
                };
                for (const id of PANEL_ORDER) {
                    const w = windows[id];
                    payload.windows[id] = {
                        homeSlotId: w.homeSlotId,
                        maximized: w.maximized,
                        floatingRect: w.floatingRect,
                        zIndex: w.zIndex,
                        visible: w.visible,
                    };
                }
                localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
            } catch {
                // ignore
            }
        }, PERSIST_DEBOUNCE_MS);
        return () => {
            if (saveTimeoutRef.current !== null) {
                window.clearTimeout(saveTimeoutRef.current);
                saveTimeoutRef.current = null;
            }
        };
    }, [windows]);

    const focus = useCallback((id: PanelId): void => {
        setFocusedId(id);
        setWindows((prev) => {
            const maxZ = Object.values(prev).reduce((acc, w) => Math.max(acc, w.zIndex), 0);
            const current = prev[id];
            if (current.zIndex === maxZ && maxZ > 0) return prev;
            return {
                ...prev,
                [id]: { ...current, zIndex: maxZ + 1 },
            };
        });
    }, []);

    const clearFocus = useCallback((): void => {
        setFocusedId(null);
    }, []);

    // Global document-level handler: clear focus when clicking outside any .window element.
    useEffect(() => {
        const onDocPointerDown = (e: PointerEvent): void => {
            const target = e.target as Element | null;
            if (!target) return;
            if (!target.closest('.window')) {
                setFocusedId(null);
            }
        };
        document.addEventListener('pointerdown', onDocPointerDown);
        return () => {
            document.removeEventListener('pointerdown', onDocPointerDown);
        };
    }, []);

    const maximize = useCallback(
        (id: PanelId): void => {
            setWindows((prev) => {
                const current = prev[id];
                if (current.maximized) return prev;
                const vw = window.innerWidth;
                const vh = window.innerHeight;
                const slotRect = computeSlot(current.homeSlotId, vw, vh);
                const rect = current.floatingRect
                    ? clampFloatingRect(current.floatingRect, vw, vh)
                    : defaultFloatingRect(slotRect, vw, vh);
                const maxZ = Object.values(prev).reduce((acc, w) => Math.max(acc, w.zIndex), 0);
                return {
                    ...prev,
                    [id]: {
                        ...current,
                        maximized: true,
                        floatingRect: rect,
                        zIndex: maxZ + 1,
                    },
                };
            });
            setFocusedId(id);
            markSettling([id]);
        },
        [markSettling],
    );

    const minimize = useCallback(
        (id: PanelId): void => {
            setWindows((prev) => {
                const current = prev[id];
                if (!current.maximized) return prev;
                return {
                    ...prev,
                    [id]: { ...current, maximized: false },
                };
            });
            markSettling([id]);
        },
        [markSettling],
    );

    const toggleMaximize = useCallback(
        (id: PanelId): void => {
            // Read current state via functional setter to avoid stale-closure race.
            setWindows((prev) => {
                const current = prev[id];
                if (current.maximized) {
                    return { ...prev, [id]: { ...current, maximized: false } };
                }
                const vw = window.innerWidth;
                const vh = window.innerHeight;
                const slotRect = computeSlot(current.homeSlotId, vw, vh);
                const rect = current.floatingRect
                    ? clampFloatingRect(current.floatingRect, vw, vh)
                    : defaultFloatingRect(slotRect, vw, vh);
                const maxZ = Object.values(prev).reduce((acc, w) => Math.max(acc, w.zIndex), 0);
                return {
                    ...prev,
                    [id]: {
                        ...current,
                        maximized: true,
                        floatingRect: rect,
                        zIndex: maxZ + 1,
                    },
                };
            });
            markSettling([id]);
        },
        [markSettling],
    );

    const move = useCallback((id: PanelId, x: number, y: number): void => {
        setWindows((prev) => {
            const current = prev[id];
            if (!current.maximized || !current.floatingRect) return prev;
            const next: FloatingRect = { ...current.floatingRect, x, y };
            return {
                ...prev,
                [id]: { ...current, floatingRect: next },
            };
        });
    }, []);

    const resize = useCallback((id: PanelId, w: number, h: number): void => {
        setWindows((prev) => {
            const current = prev[id];
            if (!current.maximized || !current.floatingRect) return prev;
            const next: FloatingRect = { ...current.floatingRect, w, h };
            return {
                ...prev,
                [id]: { ...current, floatingRect: next },
            };
        });
    }, []);

    const setActiveSnap = useCallback((region: SnapRegion | null): void => {
        setActiveSnapState((prev) => (prev === region ? prev : region));
    }, []);

    const snapWindow = useCallback(
        (id: PanelId, region: SnapRegion): void => {
            setWindows((prev) => {
                const vw = window.innerWidth;
                const vh = window.innerHeight;
                const rect = computeSnapRect(region, vw, vh);
                const current = prev[id];
                if (!current.maximized) return prev;
                const maxZ = Object.values(prev).reduce((acc, w) => Math.max(acc, w.zIndex), 0);
                return {
                    ...prev,
                    [id]: {
                        ...current,
                        floatingRect: { x: rect.x, y: rect.y, w: rect.w, h: rect.h },
                        zIndex: maxZ + 1,
                    },
                };
            });
            setFocusedId(id);
            setActiveSnapState(null);
            markSettling([id]);
        },
        [markSettling],
    );

    const swapSlots = useCallback(
        (a: PanelId, b: PanelId): void => {
            if (a === b) return;
            setWindows((prev) => {
                const wa = prev[a];
                const wb = prev[b];
                return {
                    ...prev,
                    [a]: { ...wa, homeSlotId: wb.homeSlotId },
                    [b]: { ...wb, homeSlotId: wa.homeSlotId },
                };
            });
            markSettling([a, b]);
        },
        [markSettling],
    );

    const resetWindow = useCallback(
        (id: PanelId): void => {
            setWindows((prev) => {
                const base = defaultsRef.current.get(id);
                if (!base) return prev;
                const maxZ = Object.values(prev).reduce((acc, w) => Math.max(acc, w.zIndex), 0);
                const restored: WindowState = {
                    ...base,
                    zIndex: maxZ + 1,
                };
                return { ...prev, [id]: restored };
            });
            setFocusedId(id);
            markSettling([id]);
        },
        [markSettling],
    );

    const resetAll = useCallback((): void => {
        try {
            localStorage.removeItem(STORAGE_KEY);
        } catch {
            // ignore
        }
        const fresh = computeDefaults();
        const map = new Map<PanelId, WindowState>();
        for (const id of PANEL_ORDER) {
            map.set(id, { ...fresh[id] });
        }
        defaultsRef.current = map;
        setWindows(fresh);
        setFocusedId(null);
        setActiveSnapState(null);
        markSettling(PANEL_ORDER);
    }, [markSettling]);

    // Cleanup pending settle timeouts on unmount.
    useEffect(() => {
        const timeouts = settlingTimeoutsRef.current;
        return () => {
            for (const t of timeouts.values()) {
                window.clearTimeout(t);
            }
            timeouts.clear();
        };
    }, []);

    // Viewport resize → recompute slot rects + clamp floating rects.
    useEffect(() => {
        const onResize = (): void => {
            const vw = window.innerWidth;
            const vh = window.innerHeight;
            setSlotRects(computeSlotRects(vw, vh));
            setActiveSnapState(null);
            setWindows((prev) => {
                const next = { ...prev };
                let changed = false;
                for (const id of PANEL_ORDER) {
                    const w = next[id];
                    if (!w.floatingRect) continue;
                    const clamped = clampFloatingRect(w.floatingRect, vw, vh);
                    if (
                        clamped.x !== w.floatingRect.x ||
                        clamped.y !== w.floatingRect.y ||
                        clamped.w !== w.floatingRect.w ||
                        clamped.h !== w.floatingRect.h
                    ) {
                        next[id] = { ...w, floatingRect: clamped };
                        changed = true;
                    }
                }
                return changed ? next : prev;
            });
        };
        window.addEventListener('resize', onResize);
        return () => {
            window.removeEventListener('resize', onResize);
        };
    }, []);

    const value = useMemo<WindowManagerValue>(
        () => ({
            windows,
            focusedId,
            activeSnap,
            settlingIds,
            slotRects,
            focus,
            clearFocus,
            maximize,
            minimize,
            toggleMaximize,
            move,
            resize,
            setActiveSnap,
            snapWindow,
            swapSlots,
            resetWindow,
            resetAll,
        }),
        [
            windows,
            focusedId,
            activeSnap,
            settlingIds,
            slotRects,
            focus,
            clearFocus,
            maximize,
            minimize,
            toggleMaximize,
            move,
            resize,
            setActiveSnap,
            snapWindow,
            swapSlots,
            resetWindow,
            resetAll,
        ],
    );

    return <WindowManagerContext.Provider value={value}>{children}</WindowManagerContext.Provider>;
}

export function useWindowManager(): WindowManagerValue {
    const ctx = useContext(WindowManagerContext);
    if (!ctx) {
        throw new Error('useWindowManager must be used inside <WindowManagerProvider>');
    }
    return ctx;
}

export default WindowManagerProvider;
