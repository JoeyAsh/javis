import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { type ReactElement } from 'react';
import { useSlotDrag } from '../useSlotDrag';
import type { SlotDragState } from '../useSlotDrag';
import type { SlotId } from '../../slotGrid';
import { TOP_BAR_HEIGHT, SLOT_MARGIN, COLUMN_WIDTH, BOTTOM_STRIP_HEIGHT } from '../../slotGrid';

/** Viewport size used in tests — matches SlotGrid test canonical size. */
const VW = 1440;
const VH = 900;

/** Pre-computed expected L1 centre. */
const L1_X = SLOT_MARGIN + COLUMN_WIDTH / 2;
const L1_Y = TOP_BAR_HEIGHT + SLOT_MARGIN + 50; // approximate centre

beforeEach(() => {
    HTMLElement.prototype.setPointerCapture = vi.fn();
    HTMLElement.prototype.releasePointerCapture = vi.fn();

    // Mock window dimensions so computeAllSlots inside useSlotDrag works
    Object.defineProperty(window, 'innerWidth', { value: VW, writable: true });
    Object.defineProperty(window, 'innerHeight', { value: VH, writable: true });
});

afterEach(() => {
    vi.restoreAllMocks();
});

const ASSIGNMENTS: Record<string, SlotId> = {
    'win-a': 'L1',
    'win-b': 'R1',
};

function SlotDragHost({
    windowId,
    assignments,
    onDragMove,
    onDragEnd,
}: {
    windowId: string;
    assignments: Record<string, SlotId>;
    onDragMove?: (wId: string, state: SlotDragState, e: PointerEvent) => void;
    onDragEnd?: (wId: string, state: SlotDragState, e: PointerEvent) => void;
}): ReactElement {
    const { onPointerDown, slotDragState } = useSlotDrag({
        windowId,
        assignments,
        viewportW: VW,
        viewportH: VH,
        onDragMove,
        onDragEnd,
    });

    return (
        <div
            data-testid="drag-handle"
            data-dragging={String(slotDragState.dragging)}
            data-snap={slotDragState.snapTarget ?? 'none'}
            data-swap={slotDragState.swapTarget ?? 'none'}
            onPointerDown={onPointerDown}
        >
            handle
        </div>
    );
}

function windowPointerEvent(type: string, init?: PointerEventInit): void {
    window.dispatchEvent(new PointerEvent(type, { bubbles: true, ...init }));
}

describe('useSlotDrag', () => {
    it('initial state: not dragging, no snap/swap target', () => {
        render(<SlotDragHost windowId="win-a" assignments={ASSIGNMENTS} />);
        const el = screen.getByTestId('drag-handle');
        expect(el.getAttribute('data-dragging')).toBe('false');
        expect(el.getAttribute('data-snap')).toBe('none');
        expect(el.getAttribute('data-swap')).toBe('none');
    });

    it('dragging becomes true after pointerdown', () => {
        render(<SlotDragHost windowId="win-a" assignments={ASSIGNMENTS} />);
        const el = screen.getByTestId('drag-handle');
        fireEvent.pointerDown(el, { button: 0, clientX: 100, clientY: 100 });
        expect(el.getAttribute('data-dragging')).toBe('true');
    });

    it('reports snapTarget when pointer moves over a slot', () => {
        const onDragMove = vi.fn();
        render(<SlotDragHost windowId="win-a" assignments={ASSIGNMENTS} onDragMove={onDragMove} />);
        const el = screen.getByTestId('drag-handle');
        fireEvent.pointerDown(el, { button: 0, clientX: 200, clientY: 200 });
        // Move pointer to centre of L1
        windowPointerEvent('pointermove', { clientX: L1_X, clientY: L1_Y });
        expect(onDragMove).toHaveBeenCalled();
        const [, state] = onDragMove.mock.calls[onDragMove.mock.calls.length - 1] as [
            string,
            SlotDragState,
            PointerEvent,
        ];
        expect(state.snapTarget).toBe('L1');
    });

    it('reports swapTarget when hovering an occupied slot', () => {
        const onDragMove = vi.fn();
        render(<SlotDragHost windowId="win-a" assignments={ASSIGNMENTS} onDragMove={onDragMove} />);
        const el = screen.getByTestId('drag-handle');
        fireEvent.pointerDown(el, { button: 0, clientX: 100, clientY: 100 });

        // Compute R1 centre (win-b is there).
        const R1_X =
            Math.max(SLOT_MARGIN + COLUMN_WIDTH + SLOT_MARGIN, VW - COLUMN_WIDTH - SLOT_MARGIN) +
            COLUMN_WIDTH / 2;
        const R1_Y = TOP_BAR_HEIGHT + SLOT_MARGIN + 50;
        windowPointerEvent('pointermove', { clientX: R1_X, clientY: R1_Y });

        expect(onDragMove).toHaveBeenCalled();
        const [, state] = onDragMove.mock.calls[onDragMove.mock.calls.length - 1] as [
            string,
            SlotDragState,
            PointerEvent,
        ];
        expect(state.snapTarget).toBe('R1');
        expect(state.swapTarget).toBe('win-b');
    });

    it('reports null swapTarget when hovering an empty slot', () => {
        // Use assignments where L2 is empty.
        const sparse: Record<string, SlotId> = { 'win-a': 'L1', 'win-b': 'R1' };
        const onDragMove = vi.fn();
        render(<SlotDragHost windowId="win-a" assignments={sparse} onDragMove={onDragMove} />);
        const el = screen.getByTestId('drag-handle');
        fireEvent.pointerDown(el, { button: 0, clientX: 100, clientY: 100 });

        // Move to L2 centre (no window occupies L2 in sparse)
        const L1_BOTTOM = TOP_BAR_HEIGHT + SLOT_MARGIN;
        // rough estimate of L2 y
        const cellH = Math.floor(
            (Math.max(
                60 * 3,
                VH -
                    BOTTOM_STRIP_HEIGHT -
                    SLOT_MARGIN -
                    SLOT_MARGIN -
                    TOP_BAR_HEIGHT -
                    SLOT_MARGIN -
                    SLOT_MARGIN,
            ) -
                2 * SLOT_MARGIN) /
                3,
        );
        const l2Y = L1_BOTTOM + cellH + SLOT_MARGIN + cellH / 2;
        windowPointerEvent('pointermove', { clientX: L1_X, clientY: l2Y });

        expect(onDragMove).toHaveBeenCalled();
        const [, state] = onDragMove.mock.calls[onDragMove.mock.calls.length - 1] as [
            string,
            SlotDragState,
            PointerEvent,
        ];
        // If hovered slot is L2, swapTarget should be null since no window is there.
        if (state.snapTarget === 'L2') {
            expect(state.swapTarget).toBeNull();
        }
    });

    it('calls onDragEnd with final snap/swap state on pointerup', () => {
        const onDragEnd = vi.fn();
        render(<SlotDragHost windowId="win-a" assignments={ASSIGNMENTS} onDragEnd={onDragEnd} />);
        const el = screen.getByTestId('drag-handle');
        fireEvent.pointerDown(el, { button: 0, clientX: 100, clientY: 100 });
        windowPointerEvent('pointerup', { clientX: L1_X, clientY: L1_Y });
        expect(onDragEnd).toHaveBeenCalledTimes(1);
        const [wId] = onDragEnd.mock.calls[0] as [string, SlotDragState, PointerEvent];
        expect(wId).toBe('win-a');
    });

    it('returns dragging=false after pointerup', () => {
        render(<SlotDragHost windowId="win-a" assignments={ASSIGNMENTS} />);
        const el = screen.getByTestId('drag-handle');
        fireEvent.pointerDown(el, { button: 0, clientX: 100, clientY: 100 });
        expect(el.getAttribute('data-dragging')).toBe('true');
        act(() => {
            windowPointerEvent('pointerup', { clientX: 100, clientY: 100 });
        });
        expect(el.getAttribute('data-dragging')).toBe('false');
    });
});
