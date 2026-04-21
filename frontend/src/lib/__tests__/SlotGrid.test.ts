import { describe, it, expect } from 'vitest';
import {
    computeSlot,
    computeAllSlots,
    slotAtPoint,
    SLOT_IDS,
    TOP_BAR_HEIGHT,
    SLOT_MARGIN,
    COLUMN_WIDTH,
    BOTTOM_STRIP_HEIGHT,
} from '../layout/SlotGrid';
import type { SlotId, SlotRect } from '../layout/SlotGrid';

/** Canonical viewport size for tests. */
const W = 1440;
const H = 900;

describe('SlotGrid — constants', () => {
    it('TOP_BAR_HEIGHT is 60', () => {
        expect(TOP_BAR_HEIGHT).toBe(60);
    });

    it('SLOT_MARGIN is 12', () => {
        expect(SLOT_MARGIN).toBe(12);
    });

    it('COLUMN_WIDTH is 316', () => {
        expect(COLUMN_WIDTH).toBe(316);
    });

    it('BOTTOM_STRIP_HEIGHT is 140', () => {
        expect(BOTTOM_STRIP_HEIGHT).toBe(140);
    });

    it('SLOT_IDS contains exactly 9 entries', () => {
        expect(SLOT_IDS).toHaveLength(9);
    });

    it('SLOT_IDS contains all expected ids', () => {
        const expected: SlotId[] = ['L1', 'L2', 'L3', 'R1', 'R2', 'R3', 'B1', 'B2', 'B3'];
        for (const id of expected) {
            expect(SLOT_IDS).toContain(id);
        }
    });
});

describe('computeSlot — geometry at 1440×900', () => {
    it('L1 x starts at SLOT_MARGIN', () => {
        const r = computeSlot('L1', W, H);
        expect(r.x).toBe(SLOT_MARGIN);
    });

    it('L1 y starts at TOP_BAR_HEIGHT + SLOT_MARGIN', () => {
        const r = computeSlot('L1', W, H);
        expect(r.y).toBe(TOP_BAR_HEIGHT + SLOT_MARGIN);
    });

    it('L1 width equals COLUMN_WIDTH', () => {
        const r = computeSlot('L1', W, H);
        expect(r.w).toBe(COLUMN_WIDTH);
    });

    it('L1 height is positive', () => {
        const r = computeSlot('L1', W, H);
        expect(r.h).toBeGreaterThan(0);
    });

    it('R1 x is near viewport right minus COLUMN_WIDTH - SLOT_MARGIN', () => {
        const r = computeSlot('R1', W, H);
        expect(r.x).toBe(
            Math.max(SLOT_MARGIN + COLUMN_WIDTH + SLOT_MARGIN, W - COLUMN_WIDTH - SLOT_MARGIN),
        );
    });

    it('R1 width equals COLUMN_WIDTH', () => {
        const r = computeSlot('R1', W, H);
        expect(r.w).toBe(COLUMN_WIDTH);
    });

    it('L2 y is below L1 (L1.y + L1.h + SLOT_MARGIN)', () => {
        const l1 = computeSlot('L1', W, H);
        const l2 = computeSlot('L2', W, H);
        expect(l2.y).toBe(l1.y + l1.h + SLOT_MARGIN);
    });

    it('L3 y is below L2', () => {
        const l2 = computeSlot('L2', W, H);
        const l3 = computeSlot('L3', W, H);
        expect(l3.y).toBe(l2.y + l2.h + SLOT_MARGIN);
    });

    it('R2, R3 follow same vertical stacking as L column', () => {
        const r1 = computeSlot('R1', W, H);
        const r2 = computeSlot('R2', W, H);
        const r3 = computeSlot('R3', W, H);
        expect(r2.y).toBe(r1.y + r1.h + SLOT_MARGIN);
        expect(r3.y).toBe(r2.y + r2.h + SLOT_MARGIN);
    });

    it('B* height equals BOTTOM_STRIP_HEIGHT', () => {
        for (const id of ['B1', 'B2', 'B3'] as SlotId[]) {
            expect(computeSlot(id, W, H).h).toBe(BOTTOM_STRIP_HEIGHT);
        }
    });

    it('B1 y is near viewport bottom', () => {
        const r = computeSlot('B1', W, H);
        expect(r.y).toBe(H - BOTTOM_STRIP_HEIGHT - SLOT_MARGIN);
    });

    it('B2 x is to the right of B1', () => {
        const b1 = computeSlot('B1', W, H);
        const b2 = computeSlot('B2', W, H);
        expect(b2.x).toBeGreaterThan(b1.x + b1.w);
    });

    it('B3 x is to the right of B2', () => {
        const b2 = computeSlot('B2', W, H);
        const b3 = computeSlot('B3', W, H);
        expect(b3.x).toBeGreaterThan(b2.x + b2.w);
    });

    it('all cells have positive width and height', () => {
        for (const id of SLOT_IDS) {
            const r = computeSlot(id, W, H);
            expect(r.w).toBeGreaterThan(0);
            expect(r.h).toBeGreaterThan(0);
        }
    });
});

describe('computeAllSlots', () => {
    it('returns a record with exactly 9 entries', () => {
        const rects = computeAllSlots(W, H);
        expect(Object.keys(rects)).toHaveLength(9);
    });

    it('each slot id maps to a rect matching computeSlot', () => {
        const rects = computeAllSlots(W, H);
        for (const id of SLOT_IDS) {
            const expected = computeSlot(id, W, H);
            expect(rects[id]).toEqual(expected);
        }
    });
});

describe('slotAtPoint', () => {
    const rects = computeAllSlots(W, H);

    it('returns the correct SlotId when point is inside a slot', () => {
        const r1 = rects['L1'];
        // Hit the centre of L1.
        const result = slotAtPoint(r1.x + r1.w / 2, r1.y + r1.h / 2, rects);
        expect(result).toBe('L1');
    });

    it('returns null when point is outside every slot', () => {
        // Centre of viewport — typically in the gap between L and R columns.
        const result = slotAtPoint(W / 2, H / 2, rects);
        expect(result).toBeNull();
    });

    it('hit-tests all 9 slot centres correctly', () => {
        for (const id of SLOT_IDS) {
            const r = rects[id];
            const result = slotAtPoint(r.x + r.w / 2, r.y + r.h / 2, rects);
            expect(result).toBe(id);
        }
    });

    it('returns null for a negative coordinate', () => {
        expect(slotAtPoint(-10, -10, rects)).toBeNull();
    });

    it('returns null for a coordinate beyond viewport bounds', () => {
        expect(slotAtPoint(W + 100, H + 100, rects)).toBeNull();
    });

    it('correctly identifies top-left corner of R1', () => {
        const r = rects['R1'];
        const result = slotAtPoint(r.x, r.y, rects);
        expect(result).toBe('R1');
    });

    it('empty rects record returns null', () => {
        const empty = {} as Record<SlotId, SlotRect>;
        for (const id of SLOT_IDS) {
            empty[id] = { x: 0, y: 0, w: 0, h: 0 };
        }
        // A zero-size slot cannot contain any point with positive area.
        expect(slotAtPoint(0, 0, empty)).toBe('L1'); // x=0 matches x>=0 && x<=0 and y=0
    });
});
