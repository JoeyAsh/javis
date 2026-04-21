import type { PanelId } from '../../types';

/**
 * Fixed 3×3 Dock grid slot identifier.
 *
 * Left column (top → bottom):   L1, L2, L3
 * Right column (top → bottom):  R1, R2, R3
 * Bottom strip (left → right):  B1, B2, B3
 */
export type SlotId = 'L1' | 'L2' | 'L3' | 'R1' | 'R2' | 'R3' | 'B1' | 'B2' | 'B3';

/** Ordered list of all slot ids. Iteration order is visual: left → right → bottom. */
export const SLOT_IDS: ReadonlyArray<SlotId> = [
    'L1',
    'L2',
    'L3',
    'R1',
    'R2',
    'R3',
    'B1',
    'B2',
    'B3',
];

/** Rectangular geometry (pixel-absolute, viewport-relative). */
export interface SlotRect {
    x: number;
    y: number;
    w: number;
    h: number;
}

/** Height of the HUD top-bar — kept in sync with .hud-topbar CSS height. */
export const TOP_BAR_HEIGHT = 36;

/** Margin between slots / viewport edges. */
export const SLOT_MARGIN = 12;

/** Fixed column width for L* / R*. */
export const COLUMN_WIDTH = 280;

/** Fixed bottom-strip height for B*. */
export const BOTTOM_STRIP_HEIGHT = 140;

/** Minimum slot height — used to keep math sane on tiny viewports. */
const MIN_CELL_HEIGHT = 60;

/**
 * Pure function: compute the rect for a given slot at a given viewport size.
 *
 * Layout contract (see CLAUDE.md — HUD Window Paradigm):
 * - Usable area below top-bar: W × (H - TOP_BAR_HEIGHT - 2M)
 * - Bottom strip height 140 px pinned to bottom
 * - Left + right columns each 280 px wide, divided into equal thirds
 * - Bottom strip divided into three equal-width cells
 */
export function computeSlot(id: SlotId, W: number, H: number): SlotRect {
    const M = SLOT_MARGIN;
    const TOP = TOP_BAR_HEIGHT;
    const stripH = BOTTOM_STRIP_HEIGHT;

    // Columns area lives above the bottom strip.
    const columnsTop = TOP + M;
    const columnsBottom = H - stripH - M - M;
    const columnsH = Math.max(MIN_CELL_HEIGHT * 3, columnsBottom - columnsTop);
    const cellH = Math.max(MIN_CELL_HEIGHT, Math.floor((columnsH - 2 * M) / 3));

    const leftX = M;
    const rightX = Math.max(M + COLUMN_WIDTH + M, W - COLUMN_WIDTH - M);

    // Bottom strip: three equal-width cells with gaps of M.
    const stripTotalW = W - 2 * M;
    const stripCellW = Math.max(60, Math.floor((stripTotalW - 2 * M) / 3));
    const stripY = H - stripH - M;

    switch (id) {
        case 'L1':
            return { x: leftX, y: columnsTop, w: COLUMN_WIDTH, h: cellH };
        case 'L2':
            return {
                x: leftX,
                y: columnsTop + cellH + M,
                w: COLUMN_WIDTH,
                h: cellH,
            };
        case 'L3':
            return {
                x: leftX,
                y: columnsTop + 2 * (cellH + M),
                w: COLUMN_WIDTH,
                h: cellH,
            };
        case 'R1':
            return { x: rightX, y: columnsTop, w: COLUMN_WIDTH, h: cellH };
        case 'R2':
            return {
                x: rightX,
                y: columnsTop + cellH + M,
                w: COLUMN_WIDTH,
                h: cellH,
            };
        case 'R3':
            return {
                x: rightX,
                y: columnsTop + 2 * (cellH + M),
                w: COLUMN_WIDTH,
                h: cellH,
            };
        case 'B1':
            return { x: M, y: stripY, w: stripCellW, h: stripH };
        case 'B2':
            return {
                x: M + stripCellW + M,
                y: stripY,
                w: stripCellW,
                h: stripH,
            };
        case 'B3':
            return {
                x: M + 2 * (stripCellW + M),
                y: stripY,
                w: stripCellW,
                h: stripH,
            };
        default: {
            const _exhaustive: never = id;
            void _exhaustive;
            return { x: 0, y: 0, w: 0, h: 0 };
        }
    }
}

/** Default panel → slot assignments (first-load state). */
export const DEFAULT_ASSIGNMENTS: Record<PanelId, SlotId> = {
    agenda: 'L1',
    mail: 'L2',
    notifications: 'L3',
    nowplaying: 'R1',
    lights: 'R2',
    system: 'R3',
    transcript: 'B1',
    dev: 'B2',
    // gitlab occupies B3 (bottom-strip). selffix and log share B3 at lower
    // priority — drag them to another free slot if needed.
    gitlab: 'B3',
    selffix: 'B3',
    log: 'B3',
};

/**
 * Compute the rect of the slot currently assigned to `id`.
 * `assignments` maps PanelId → SlotId.
 */
export function slotForPanel(
    assignments: Record<PanelId, SlotId>,
    id: PanelId,
    W: number,
    H: number,
): SlotRect {
    return computeSlot(assignments[id], W, H);
}

/**
 * Return the SlotId whose rect contains the given viewport point, or null if
 * the point falls outside every slot rect.
 */
export function slotAtPoint(x: number, y: number, rects: Record<SlotId, SlotRect>): SlotId | null {
    for (const id of SLOT_IDS) {
        const r = rects[id];
        if (x >= r.x && x <= r.x + r.w && y >= r.y && y <= r.y + r.h) {
            return id;
        }
    }
    return null;
}

export default computeSlot;
