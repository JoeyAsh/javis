import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, fireEvent, act } from '@testing-library/react';
import { WindowManager } from '../WindowManager';
import type { ManagedWindow } from '../WindowManager';
import type { SlotId } from '../../layout/SlotGrid';
import { computeAllSlots, SLOT_MARGIN, TOP_BAR_HEIGHT, COLUMN_WIDTH } from '../../layout/SlotGrid';

/** Viewport used in all tests. */
const VW = 1280;
const VH = 900;

/** Mock PointerEvent dispatch on window. */
function windowPointerEvent(type: string, init?: PointerEventInit): void {
    window.dispatchEvent(new PointerEvent(type, { bubbles: true, ...init }));
}

const WIN_A: ManagedWindow = { id: 'win-a', title: 'Alpha', content: <div>Alpha body</div> };
const WIN_B: ManagedWindow = { id: 'win-b', title: 'Bravo', content: <div>Bravo body</div> };

beforeEach(() => {
    HTMLElement.prototype.setPointerCapture = vi.fn();
    HTMLElement.prototype.releasePointerCapture = vi.fn();

    Object.defineProperty(window, 'innerWidth', { value: VW, writable: true, configurable: true });
    Object.defineProperty(window, 'innerHeight', { value: VH, writable: true, configurable: true });
    // Trigger resize so the component reads the mocked dimensions.
    act(() => {
        window.dispatchEvent(new Event('resize'));
    });
});

afterEach(() => {
    vi.restoreAllMocks();
});

describe('WindowManager — rendering', () => {
    it('renders without crashing', () => {
        const { container } = render(
            <WindowManager
                windows={[WIN_A]}
                assignments={{ 'win-a': 'L1' }}
                onAssignmentsChange={vi.fn()}
            />,
        );
        expect(container.querySelector('.lib-wm')).toBeDefined();
    });

    it('renders one window per entry in windows + assignments', () => {
        const { container } = render(
            <WindowManager
                windows={[WIN_A, WIN_B]}
                assignments={{ 'win-a': 'L1', 'win-b': 'R1' }}
                onAssignmentsChange={vi.fn()}
            />,
        );
        expect(container.querySelectorAll('.lib-window')).toHaveLength(2);
    });

    it('does not render window whose id is absent from assignments', () => {
        const { container } = render(
            <WindowManager
                windows={[WIN_A, WIN_B]}
                assignments={{ 'win-a': 'L1' }}
                onAssignmentsChange={vi.fn()}
            />,
        );
        expect(container.querySelectorAll('.lib-window')).toHaveLength(1);
    });

    it('renders windows at slot-derived positions', () => {
        const { container } = render(
            <WindowManager
                windows={[WIN_A]}
                assignments={{ 'win-a': 'L1' }}
                onAssignmentsChange={vi.fn()}
            />,
        );
        const rects = computeAllSlots(VW, VH);
        const l1 = rects['L1'];
        const win = container.querySelector<HTMLDivElement>('[data-window-id="win-a"]');
        expect(win?.style.left).toBe(`${l1.x}px`);
        expect(win?.style.top).toBe(`${l1.y}px`);
        expect(win?.style.width).toBe(`${l1.w}px`);
        expect(win?.style.height).toBe(`${l1.h}px`);
    });

    it('renders title of each window', () => {
        const { getByText } = render(
            <WindowManager
                windows={[WIN_A, WIN_B]}
                assignments={{ 'win-a': 'L1', 'win-b': 'R1' }}
                onAssignmentsChange={vi.fn()}
            />,
        );
        expect(getByText('Alpha')).toBeDefined();
        expect(getByText('Bravo')).toBeDefined();
    });

    it('merges className on root', () => {
        const { container } = render(
            <WindowManager
                windows={[WIN_A]}
                assignments={{ 'win-a': 'L1' }}
                onAssignmentsChange={vi.fn()}
                className="extra"
            />,
        );
        expect(container.querySelector('.lib-wm')?.classList.contains('extra')).toBe(true);
    });

    it('renders SnapOverlay element', () => {
        const { container } = render(
            <WindowManager
                windows={[WIN_A]}
                assignments={{ 'win-a': 'L1' }}
                onAssignmentsChange={vi.fn()}
            />,
        );
        expect(container.querySelector('.lib-snap')).toBeDefined();
    });

    it('renders SwapOverlay element', () => {
        const { container } = render(
            <WindowManager
                windows={[WIN_A]}
                assignments={{ 'win-a': 'L1' }}
                onAssignmentsChange={vi.fn()}
            />,
        );
        expect(container.querySelector('.lib-swap')).toBeDefined();
    });
});

describe('WindowManager — focus', () => {
    it('clicking a window calls onFocusChange with its id', () => {
        const onFocusChange = vi.fn();
        const { container } = render(
            <WindowManager
                windows={[WIN_A]}
                assignments={{ 'win-a': 'L1' }}
                onAssignmentsChange={vi.fn()}
                onFocusChange={onFocusChange}
            />,
        );
        const win = container.querySelector('[data-window-id="win-a"]') as HTMLElement;
        fireEvent.pointerDown(win);
        expect(onFocusChange).toHaveBeenCalledWith('win-a');
    });

    it('focused window has data-state="focused"', () => {
        const { container } = render(
            <WindowManager
                windows={[WIN_A]}
                assignments={{ 'win-a': 'L1' }}
                onAssignmentsChange={vi.fn()}
                focusedId="win-a"
            />,
        );
        const win = container.querySelector('[data-window-id="win-a"]');
        expect(win?.getAttribute('data-state')).toBe('focused');
    });
});

describe('WindowManager — drag-drop: move to empty slot', () => {
    it('dropping on empty slot calls onAssignmentsChange with new slot', () => {
        const onAssignmentsChange = vi.fn();
        const { container } = render(
            <WindowManager
                windows={[WIN_A]}
                assignments={{ 'win-a': 'L1' }}
                onAssignmentsChange={onAssignmentsChange}
            />,
        );

        const rects = computeAllSlots(VW, VH);
        const l2 = rects['L2'];
        // Centre of L2
        const dropX = l2.x + l2.w / 2;
        const dropY = l2.y + l2.h / 2;

        // Start drag on win-a's header
        const handle = container.querySelector('[data-testid="window-drag-handle"]') as HTMLElement;
        fireEvent.pointerDown(handle, { button: 0, clientX: 50, clientY: 80 });

        act(() => {
            windowPointerEvent('pointermove', { clientX: dropX, clientY: dropY });
        });
        act(() => {
            windowPointerEvent('pointerup', { clientX: dropX, clientY: dropY });
        });

        expect(onAssignmentsChange).toHaveBeenCalledOnce();
        const [next] = onAssignmentsChange.mock.calls[0] as [Record<string, SlotId>];
        expect(next['win-a']).toBe('L2');
    });

    it('dropping on own slot does not fire onAssignmentsChange', () => {
        const onAssignmentsChange = vi.fn();
        const { container } = render(
            <WindowManager
                windows={[WIN_A]}
                assignments={{ 'win-a': 'L1' }}
                onAssignmentsChange={onAssignmentsChange}
            />,
        );

        const rects = computeAllSlots(VW, VH);
        const l1 = rects['L1'];
        const dropX = l1.x + l1.w / 2;
        const dropY = l1.y + l1.h / 2;

        const handle = container.querySelector('[data-testid="window-drag-handle"]') as HTMLElement;
        fireEvent.pointerDown(handle, { button: 0, clientX: dropX, clientY: dropY });
        act(() => {
            windowPointerEvent('pointerup', { clientX: dropX, clientY: dropY });
        });

        expect(onAssignmentsChange).not.toHaveBeenCalled();
    });
});

describe('WindowManager — drag-drop: swap with occupied slot', () => {
    it('dropping on occupied slot swaps assignments', () => {
        const onAssignmentsChange = vi.fn();
        const { container } = render(
            <WindowManager
                windows={[WIN_A, WIN_B]}
                assignments={{ 'win-a': 'L1', 'win-b': 'R1' }}
                onAssignmentsChange={onAssignmentsChange}
            />,
        );

        const rects = computeAllSlots(VW, VH);
        const r1 = rects['R1'];
        const dropX = r1.x + r1.w / 2;
        const dropY = r1.y + r1.h / 2;

        // Drag win-a over R1 (which has win-b)
        const handles = container.querySelectorAll('[data-testid="window-drag-handle"]');
        // First handle belongs to win-a (renders first in DOM)
        const handleA = handles[0] as HTMLElement;
        fireEvent.pointerDown(handleA, { button: 0, clientX: 50, clientY: 80 });
        act(() => {
            windowPointerEvent('pointermove', { clientX: dropX, clientY: dropY });
        });
        act(() => {
            windowPointerEvent('pointerup', { clientX: dropX, clientY: dropY });
        });

        expect(onAssignmentsChange).toHaveBeenCalledOnce();
        const [next] = onAssignmentsChange.mock.calls[0] as [Record<string, SlotId>];
        expect(next['win-a']).toBe('R1');
        expect(next['win-b']).toBe('L1');
    });
});

describe('WindowManager — drag-drop: outside any slot', () => {
    it('dropping outside any slot does not fire onAssignmentsChange', () => {
        const onAssignmentsChange = vi.fn();
        const { container } = render(
            <WindowManager
                windows={[WIN_A]}
                assignments={{ 'win-a': 'L1' }}
                onAssignmentsChange={onAssignmentsChange}
            />,
        );

        // The centre of the viewport (1280/2, 900/2 = 640, 450) is between
        // the left and right columns — should be outside every slot.
        const handle = container.querySelector('[data-testid="window-drag-handle"]') as HTMLElement;
        fireEvent.pointerDown(handle, { button: 0, clientX: 50, clientY: 80 });
        act(() => {
            windowPointerEvent('pointermove', { clientX: VW / 2, clientY: VH / 2 });
        });
        act(() => {
            windowPointerEvent('pointerup', { clientX: VW / 2, clientY: VH / 2 });
        });

        expect(onAssignmentsChange).not.toHaveBeenCalled();
    });
});

describe('WindowManager — resize updates slot positions', () => {
    it('re-renders windows at new slot positions after viewport resize', () => {
        const { container } = render(
            <WindowManager
                windows={[WIN_A]}
                assignments={{ 'win-a': 'L1' }}
                onAssignmentsChange={vi.fn()}
            />,
        );

        const NEW_W = 1600;
        const NEW_H = 1000;

        act(() => {
            Object.defineProperty(window, 'innerWidth', {
                value: NEW_W,
                writable: true,
                configurable: true,
            });
            Object.defineProperty(window, 'innerHeight', {
                value: NEW_H,
                writable: true,
                configurable: true,
            });
            window.dispatchEvent(new Event('resize'));
        });

        const rects = computeAllSlots(NEW_W, NEW_H);
        const l1 = rects['L1'];
        const leftX = SLOT_MARGIN;
        const topY = TOP_BAR_HEIGHT + SLOT_MARGIN;
        expect(l1.x).toBe(leftX);
        expect(l1.y).toBe(topY);
        expect(l1.w).toBe(COLUMN_WIDTH);

        const win = container.querySelector<HTMLDivElement>('[data-window-id="win-a"]');
        expect(win?.style.left).toBe(`${l1.x}px`);
        expect(win?.style.top).toBe(`${l1.y}px`);
    });
});
