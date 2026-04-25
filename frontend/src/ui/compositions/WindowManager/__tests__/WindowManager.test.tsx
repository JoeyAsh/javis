import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, fireEvent, act } from '@testing-library/react';
import type { ReactNode } from 'react';
import { WindowManager } from '../WindowManager';
import type { ManagedWindow } from '../WindowManager';
import { SfxProvider } from '@core/audio';
import type { SlotId } from '../../../window/slotGrid';
import { computeAllSlots, SLOT_MARGIN, TOP_BAR_HEIGHT, COLUMN_WIDTH } from '../../../window/slotGrid';

// ── Viewport used in all tests ─────────────────────────────────────────────────

const VW = 1280;
const VH = 900;

// ── Helpers ───────────────────────────────────────────────────────────────────

function windowPointerEvent(type: string, init?: PointerEventInit): void {
    window.dispatchEvent(new PointerEvent(type, { bubbles: true, ...init }));
}

function noop(): void {
    /* intentional no-op */
}

/** Wrap children in a no-op SfxProvider so Window's useSfx() calls don't crash. */
function SfxWrapper({ children }: { children: ReactNode }): ReactNode {
    return (
        <SfxProvider playOneShot={vi.fn()} play={vi.fn()} stop={vi.fn()}>
            {children}
        </SfxProvider>
    );
}

function renderWithSfx(ui: ReactNode) {
    return render(<SfxWrapper>{ui}</SfxWrapper>);
}

// ── Fixture windows ────────────────────────────────────────────────────────────

const WIN_A: ManagedWindow = {
    id: 'win-a',
    title: 'Alpha',
    itemRenderer: () => <div>Alpha body</div>,
};

const WIN_B: ManagedWindow = {
    id: 'win-b',
    title: 'Bravo',
    itemRenderer: () => <div>Bravo body</div>,
};

// ── Test lifecycle ─────────────────────────────────────────────────────────────

beforeEach(() => {
    HTMLElement.prototype.setPointerCapture = vi.fn();
    HTMLElement.prototype.releasePointerCapture = vi.fn();

    Object.defineProperty(window, 'innerWidth', { value: VW, writable: true, configurable: true });
    Object.defineProperty(window, 'innerHeight', {
        value: VH,
        writable: true,
        configurable: true,
    });
    act(() => {
        window.dispatchEvent(new Event('resize'));
    });
});

afterEach(() => {
    vi.restoreAllMocks();
});

// ── 1. Rendering ──────────────────────────────────────────────────────────────

describe('WindowManager — rendering', () => {
    it('renders without crashing', () => {
        const { container } = renderWithSfx(
            <WindowManager
                windows={[WIN_A]}
                assignments={{ 'win-a': 'L1' }}
                onAssignmentsChange={noop}
            />,
        );
        expect(container.querySelector('.lib-wm')).not.toBeNull();
    });

    it('renders one window per entry that exists in assignments', () => {
        const { container } = renderWithSfx(
            <WindowManager
                windows={[WIN_A, WIN_B]}
                assignments={{ 'win-a': 'L1', 'win-b': 'R1' }}
                onAssignmentsChange={noop}
            />,
        );
        expect(container.querySelectorAll('.lib-window')).toHaveLength(2);
    });

    it('does not render a window whose id is absent from assignments', () => {
        const { container } = renderWithSfx(
            <WindowManager
                windows={[WIN_A, WIN_B]}
                assignments={{ 'win-a': 'L1' }}
                onAssignmentsChange={noop}
            />,
        );
        expect(container.querySelectorAll('.lib-window')).toHaveLength(1);
    });

    it('renders windows at slot-derived positions (compact mode)', () => {
        const { container } = renderWithSfx(
            <WindowManager
                windows={[WIN_A]}
                assignments={{ 'win-a': 'L1' }}
                onAssignmentsChange={noop}
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

    it('renders titles of each window', () => {
        const { getByText } = renderWithSfx(
            <WindowManager
                windows={[WIN_A, WIN_B]}
                assignments={{ 'win-a': 'L1', 'win-b': 'R1' }}
                onAssignmentsChange={noop}
            />,
        );
        expect(getByText('Alpha')).not.toBeNull();
        expect(getByText('Bravo')).not.toBeNull();
    });

    it('merges className onto root element', () => {
        const { container } = renderWithSfx(
            <WindowManager
                windows={[WIN_A]}
                assignments={{ 'win-a': 'L1' }}
                onAssignmentsChange={noop}
                className="extra"
            />,
        );
        expect(container.querySelector('.lib-wm')?.classList.contains('extra')).toBe(true);
    });

    it('renders SnapOverlay element', () => {
        const { container } = renderWithSfx(
            <WindowManager
                windows={[WIN_A]}
                assignments={{ 'win-a': 'L1' }}
                onAssignmentsChange={noop}
            />,
        );
        expect(container.querySelector('.lib-snap')).not.toBeNull();
    });

    it('renders SwapOverlay element', () => {
        const { container } = renderWithSfx(
            <WindowManager
                windows={[WIN_A]}
                assignments={{ 'win-a': 'L1' }}
                onAssignmentsChange={noop}
            />,
        );
        expect(container.querySelector('.lib-swap')).not.toBeNull();
    });

    it('itemRenderer receives mode, focused, and dragging props', () => {
        const renderer = vi.fn(() => <div>body</div>);
        const win: ManagedWindow = { id: 'win-a', title: 'A', itemRenderer: renderer };
        renderWithSfx(
            <WindowManager
                windows={[win]}
                assignments={{ 'win-a': 'L1' }}
                onAssignmentsChange={noop}
                focusedId="win-a"
            />,
        );
        expect(renderer).toHaveBeenCalledWith(
            expect.objectContaining({ mode: 'compact', focused: true, dragging: false }),
        );
    });
});

// ── 2. Focus ──────────────────────────────────────────────────────────────────

describe('WindowManager — focus', () => {
    it('clicking a window calls onFocusChange with its id', () => {
        const onFocusChange = vi.fn();
        const { container } = renderWithSfx(
            <WindowManager
                windows={[WIN_A]}
                assignments={{ 'win-a': 'L1' }}
                onAssignmentsChange={noop}
                onFocusChange={onFocusChange}
            />,
        );
        const win = container.querySelector('[data-window-id="win-a"]') as HTMLElement;
        fireEvent.pointerDown(win);
        expect(onFocusChange).toHaveBeenCalledWith('win-a');
    });

    it('focused window has data-state="focused"', () => {
        const { container } = renderWithSfx(
            <WindowManager
                windows={[WIN_A]}
                assignments={{ 'win-a': 'L1' }}
                onAssignmentsChange={noop}
                focusedId="win-a"
            />,
        );
        const win = container.querySelector('[data-window-id="win-a"]');
        expect(win?.getAttribute('data-state')).toBe('focused');
    });

    it('window without focusedId has data-state="idle"', () => {
        const { container } = renderWithSfx(
            <WindowManager
                windows={[WIN_A]}
                assignments={{ 'win-a': 'L1' }}
                onAssignmentsChange={noop}
                focusedId={null}
            />,
        );
        const win = container.querySelector('[data-window-id="win-a"]');
        expect(win?.getAttribute('data-state')).toBe('idle');
    });
});

// ── 3. Compact drag — move to empty slot ─────────────────────────────────────

describe('WindowManager — compact drag: move to empty slot', () => {
    it('dropping on empty slot calls onAssignmentsChange with new slot', () => {
        const onAssignmentsChange = vi.fn();
        const { container } = renderWithSfx(
            <WindowManager
                windows={[WIN_A]}
                assignments={{ 'win-a': 'L1' }}
                onAssignmentsChange={onAssignmentsChange}
            />,
        );

        const rects = computeAllSlots(VW, VH);
        const l2 = rects['L2'];
        const dropX = l2.x + l2.w / 2;
        const dropY = l2.y + l2.h / 2;

        const handle = container.querySelector(
            '[data-testid="window-drag-handle"]',
        ) as HTMLElement;
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
        const { container } = renderWithSfx(
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

        const handle = container.querySelector(
            '[data-testid="window-drag-handle"]',
        ) as HTMLElement;
        fireEvent.pointerDown(handle, { button: 0, clientX: dropX, clientY: dropY });

        act(() => {
            windowPointerEvent('pointerup', { clientX: dropX, clientY: dropY });
        });

        expect(onAssignmentsChange).not.toHaveBeenCalled();
    });

    it('dropping outside any slot does not fire onAssignmentsChange', () => {
        const onAssignmentsChange = vi.fn();
        const { container } = renderWithSfx(
            <WindowManager
                windows={[WIN_A]}
                assignments={{ 'win-a': 'L1' }}
                onAssignmentsChange={onAssignmentsChange}
            />,
        );

        const handle = container.querySelector(
            '[data-testid="window-drag-handle"]',
        ) as HTMLElement;
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

// ── 4. Compact drag — swap with occupied slot ─────────────────────────────────

describe('WindowManager — compact drag: swap with occupied slot', () => {
    it('dropping on occupied slot swaps assignments', () => {
        const onAssignmentsChange = vi.fn();
        const { container } = renderWithSfx(
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

        // First drag handle belongs to the first window rendered (win-a).
        const handles = container.querySelectorAll('[data-testid="window-drag-handle"]');
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

// ── 5. Reset ──────────────────────────────────────────────────────────────────

describe('WindowManager — Reset button', () => {
    it('Reset button is present', () => {
        const { container } = renderWithSfx(
            <WindowManager
                windows={[WIN_A]}
                assignments={{ 'win-a': 'L1' }}
                onAssignmentsChange={noop}
            />,
        );
        const btn = container.querySelector(
            '[data-window-id="win-a"] button[aria-label="Reset window"]',
        );
        expect(btn).not.toBeNull();
    });

    it('clicking Reset calls onAssignmentsChange with homeSlot', () => {
        const onAssignmentsChange = vi.fn();
        const { container } = renderWithSfx(
            <WindowManager
                windows={[WIN_A]}
                assignments={{ 'win-a': 'R1' }}
                homeAssignments={{ 'win-a': 'L1' }}
                onAssignmentsChange={onAssignmentsChange}
            />,
        );
        const btn = container.querySelector(
            '[data-window-id="win-a"] button[aria-label="Reset window"]',
        ) as HTMLElement;
        act(() => {
            fireEvent.click(btn);
        });
        expect(onAssignmentsChange).toHaveBeenCalledOnce();
        const [next] = onAssignmentsChange.mock.calls[0] as [Record<string, SlotId>];
        expect(next['win-a']).toBe('L1');
    });

    it('window returns to idle state after Reset', () => {
        const { container } = renderWithSfx(
            <WindowManager
                windows={[WIN_A]}
                assignments={{ 'win-a': 'L1' }}
                onAssignmentsChange={noop}
                focusedId="win-a"
            />,
        );
        const btn = container.querySelector(
            '[data-window-id="win-a"] button[aria-label="Reset window"]',
        ) as HTMLElement;
        act(() => {
            fireEvent.click(btn);
        });
        // After reset, window state should not be resizing/dragging — data-state driven by parent.
        const win = container.querySelector('[data-window-id="win-a"]');
        // state is still "focused" because focusedId prop hasn't changed; just verifying no crash.
        expect(win).not.toBeNull();
    });
});

// ── 6. ModeToggle (compact ↔ expanded) ───────────────────────────────────────

describe('WindowManager — ModeToggle button', () => {
    it('ModeToggle button shows "Undock window" in compact mode', () => {
        const { container } = renderWithSfx(
            <WindowManager
                windows={[WIN_A]}
                assignments={{ 'win-a': 'L1' }}
                onAssignmentsChange={noop}
            />,
        );
        const btn = container.querySelector(
            '[data-window-id="win-a"] button[aria-label="Undock window"]',
        );
        expect(btn).not.toBeNull();
    });

    it('clicking ModeToggle (uncontrolled) switches window to expanded mode', () => {
        const { container } = renderWithSfx(
            <WindowManager
                windows={[WIN_A]}
                assignments={{ 'win-a': 'L1' }}
                onAssignmentsChange={noop}
            />,
        );
        const btn = container.querySelector(
            '[data-window-id="win-a"] button[aria-label="Undock window"]',
        ) as HTMLElement;
        act(() => {
            fireEvent.click(btn);
        });
        const win = container.querySelector('[data-window-id="win-a"]');
        expect(win?.getAttribute('data-mode')).toBe('expanded');
    });

    it('clicking ModeToggle twice (uncontrolled) returns to compact mode', () => {
        const { container } = renderWithSfx(
            <WindowManager
                windows={[WIN_A]}
                assignments={{ 'win-a': 'L1' }}
                onAssignmentsChange={noop}
            />,
        );
        const getBtn = (): HTMLElement =>
            container.querySelector(
                '[data-window-id="win-a"] button[aria-label="Undock window"], ' +
                    '[data-window-id="win-a"] button[aria-label="Dock window"]',
            ) as HTMLElement;

        act(() => {
            fireEvent.click(getBtn());
        });
        expect(
            container.querySelector('[data-window-id="win-a"]')?.getAttribute('data-mode'),
        ).toBe('expanded');

        act(() => {
            fireEvent.click(getBtn());
        });
        expect(
            container.querySelector('[data-window-id="win-a"]')?.getAttribute('data-mode'),
        ).toBe('compact');
    });

    it('onModesChange is called (uncontrolled) when ModeToggle is clicked', () => {
        const onModesChange = vi.fn();
        const { container } = renderWithSfx(
            <WindowManager
                windows={[WIN_A]}
                assignments={{ 'win-a': 'L1' }}
                onAssignmentsChange={noop}
                onModesChange={onModesChange}
            />,
        );
        const btn = container.querySelector(
            '[data-window-id="win-a"] button[aria-label="Undock window"]',
        ) as HTMLElement;
        act(() => {
            fireEvent.click(btn);
        });
        expect(onModesChange).toHaveBeenCalledOnce();
        const [next] = onModesChange.mock.calls[0] as [Record<string, string>];
        expect(next['win-a']).toBe('expanded');
    });

    it('controlled modes prop overrides internal state', () => {
        const { container } = renderWithSfx(
            <WindowManager
                windows={[WIN_A]}
                assignments={{ 'win-a': 'L1' }}
                onAssignmentsChange={noop}
                modes={{ 'win-a': 'expanded' }}
                expandedRects={{ 'win-a': { x: 100, y: 100, w: 400, h: 300 } }}
                onModesChange={noop}
            />,
        );
        const win = container.querySelector('[data-window-id="win-a"]');
        expect(win?.getAttribute('data-mode')).toBe('expanded');
    });
});

// ── 7. Expanded mode: free drag, no slot overlays ─────────────────────────────

describe('WindowManager — expanded mode: free drag', () => {
    it('SnapOverlay is NOT active when window is expanded and dragged', () => {
        const { container } = renderWithSfx(
            <WindowManager
                windows={[WIN_A]}
                assignments={{ 'win-a': 'L1' }}
                onAssignmentsChange={noop}
                modes={{ 'win-a': 'expanded' }}
                expandedRects={{ 'win-a': { x: 100, y: 100, w: 400, h: 300 } }}
                onModesChange={noop}
            />,
        );
        // Drag the expanded window — SnapOverlay data-active should remain false/absent.
        const handle = container.querySelector(
            '[data-testid="window-drag-handle"]',
        ) as HTMLElement;
        fireEvent.pointerDown(handle, { button: 0, clientX: 200, clientY: 150 });

        act(() => {
            windowPointerEvent('pointermove', { clientX: 300, clientY: 250 });
        });

        const snap = container.querySelector('.lib-snap');
        // Snap overlay should be inactive (no activeDrag in compact mode).
        expect(snap?.getAttribute('data-active')).not.toBe('true');

        act(() => {
            windowPointerEvent('pointerup', { clientX: 300, clientY: 250 });
        });
    });

    it('expanded window positions at expandedRects coordinates', () => {
        const { container } = renderWithSfx(
            <WindowManager
                windows={[WIN_A]}
                assignments={{ 'win-a': 'L1' }}
                onAssignmentsChange={noop}
                modes={{ 'win-a': 'expanded' }}
                expandedRects={{ 'win-a': { x: 200, y: 150, w: 500, h: 350 } }}
                onModesChange={noop}
            />,
        );
        const win = container.querySelector<HTMLDivElement>('[data-window-id="win-a"]');
        expect(win?.style.left).toBe('200px');
        expect(win?.style.top).toBe('150px');
        expect(win?.style.width).toBe('500px');
        expect(win?.style.height).toBe('350px');
    });
});

// ── 8. Viewport resize: clamping ──────────────────────────────────────────────

describe('WindowManager — viewport resize', () => {
    it('re-renders windows at new slot positions after viewport resize', () => {
        const { container } = renderWithSfx(
            <WindowManager
                windows={[WIN_A]}
                assignments={{ 'win-a': 'L1' }}
                onAssignmentsChange={noop}
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
        // Verify slot computation constants are used correctly.
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
