/**
 * Fixed 3×3 Dock grid slot geometry.
 *
 * Left column (top → bottom):   L1, L2, L3
 * Right column (top → bottom):  R1, R2, R3
 * Bottom strip (left → right):  B1, B2, B3
 */

export type SlotId = 'L1' | 'L2' | 'L3' | 'R1' | 'R2' | 'R3' | 'B1' | 'B2' | 'B3';

/** Ordered list of all slot ids (visual: left → right → bottom). */
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

/**
 * Height of the HUD top-bar area:
 *   10 px top-offset + 40 px bar height + 10 px margin below = 60 px.
 */
export const TOP_BAR_HEIGHT = 60;

/** Gap between slots / viewport edges. */
export const SLOT_MARGIN = 12;

/** Fixed column width for L* / R* slots — matches System Vitals handoff width. */
export const COLUMN_WIDTH = 316;

/** Fixed bottom-strip height for B* slots. */
export const BOTTOM_STRIP_HEIGHT = 140;

/** Minimum per-cell height — prevents degenerate layout on small viewports. */
const MIN_CELL_HEIGHT = 60;

/**
 * Pure function: compute the rect for a given slot id at a given viewport size.
 */
export function computeSlot(id: SlotId, W: number, H: number): SlotRect {
    const M = SLOT_MARGIN;
    const stripH = BOTTOM_STRIP_HEIGHT;

    const columnsTop = TOP_BAR_HEIGHT + M;
    const columnsBottom = H - stripH - M - M;
    const columnsH = Math.max(MIN_CELL_HEIGHT * 3, columnsBottom - columnsTop);
    const cellH = Math.max(MIN_CELL_HEIGHT, Math.floor((columnsH - 2 * M) / 3));

    const leftX = M;
    const rightX = Math.max(M + COLUMN_WIDTH + M, W - COLUMN_WIDTH - M);

    const stripTotalW = W - 2 * M;
    const stripCellW = Math.max(60, Math.floor((stripTotalW - 2 * M) / 3));
    const stripY = H - stripH - M;

    switch (id) {
        case 'L1':
            return { x: leftX, y: columnsTop, w: COLUMN_WIDTH, h: cellH };
        case 'L2':
            return { x: leftX, y: columnsTop + cellH + M, w: COLUMN_WIDTH, h: cellH };
        case 'L3':
            return { x: leftX, y: columnsTop + 2 * (cellH + M), w: COLUMN_WIDTH, h: cellH };
        case 'R1':
            return { x: rightX, y: columnsTop, w: COLUMN_WIDTH, h: cellH };
        case 'R2':
            return { x: rightX, y: columnsTop + cellH + M, w: COLUMN_WIDTH, h: cellH };
        case 'R3':
            return { x: rightX, y: columnsTop + 2 * (cellH + M), w: COLUMN_WIDTH, h: cellH };
        case 'B1':
            return { x: M, y: stripY, w: stripCellW, h: stripH };
        case 'B2':
            return { x: M + stripCellW + M, y: stripY, w: stripCellW, h: stripH };
        case 'B3':
            return { x: M + 2 * (stripCellW + M), y: stripY, w: stripCellW, h: stripH };
        default: {
            const _exhaustive: never = id;
            void _exhaustive;
            return { x: 0, y: 0, w: 0, h: 0 };
        }
    }
}

/**
 * Return the SlotId whose rect contains the viewport point (x, y), or null if
 * the point falls outside every slot.
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

/**
 * Compute all 9 slot rects for a given viewport size.
 */
export function computeAllSlots(W: number, H: number): Record<SlotId, SlotRect> {
    const out = {} as Record<SlotId, SlotRect>;
    for (const id of SLOT_IDS) {
        out[id] = computeSlot(id, W, H);
    }
    return out;
}

export default computeSlot;
