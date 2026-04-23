import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { type ReactElement } from 'react';
import { useDraggable } from '../useDraggable';
import type { DragState } from '../useDraggable';

/** Simple component that uses useDraggable on a div. */
function DragHandle({
    onStart,
    onMove,
    onEnd,
    disabled,
}: {
    onStart?: (e: PointerEvent) => void;
    onMove?: (state: DragState, e: PointerEvent) => void;
    onEnd?: (state: DragState, e: PointerEvent) => void;
    disabled?: boolean;
}): ReactElement {
    const { onPointerDown, dragging } = useDraggable({ onStart, onMove, onEnd, disabled });
    return (
        <div
            data-testid="handle"
            data-dragging={dragging ? 'true' : 'false'}
            onPointerDown={onPointerDown}
        >
            handle
        </div>
    );
}

/** Helper to fire a native PointerEvent on window. */
function windowPointerEvent(type: string, init?: PointerEventInit): void {
    window.dispatchEvent(new PointerEvent(type, { bubbles: true, ...init }));
}

beforeEach(() => {
    // Mock setPointerCapture on HTMLElement so it doesn't throw in jsdom.
    HTMLElement.prototype.setPointerCapture = vi.fn();
    HTMLElement.prototype.releasePointerCapture = vi.fn();
});

afterEach(() => {
    vi.restoreAllMocks();
});

describe('useDraggable', () => {
    it('renders the handle without dragging', () => {
        render(<DragHandle />);
        const el = screen.getByTestId('handle');
        expect(el.getAttribute('data-dragging')).toBe('false');
    });

    it('calls onStart when pointer is pressed', () => {
        const onStart = vi.fn();
        render(<DragHandle onStart={onStart} />);
        const el = screen.getByTestId('handle');
        fireEvent.pointerDown(el, { button: 0, clientX: 10, clientY: 20 });
        expect(onStart).toHaveBeenCalledTimes(1);
        expect(onStart.mock.calls[0][0]).toBeInstanceOf(PointerEvent);
    });

    it('calls onMove with correct dx/dy during pointer move', () => {
        const onMove = vi.fn();
        render(<DragHandle onMove={onMove} />);
        const el = screen.getByTestId('handle');
        fireEvent.pointerDown(el, { button: 0, clientX: 100, clientY: 200 });
        windowPointerEvent('pointermove', { clientX: 115, clientY: 230 });
        expect(onMove).toHaveBeenCalledTimes(1);
        const [state] = onMove.mock.calls[0] as [DragState, PointerEvent];
        expect(state.dx).toBe(15);
        expect(state.dy).toBe(30);
        expect(state.dragging).toBe(true);
    });

    it('calls onEnd when pointer is released', () => {
        const onEnd = vi.fn();
        render(<DragHandle onEnd={onEnd} />);
        const el = screen.getByTestId('handle');
        fireEvent.pointerDown(el, { button: 0, clientX: 50, clientY: 50 });
        windowPointerEvent('pointerup', { clientX: 60, clientY: 70 });
        expect(onEnd).toHaveBeenCalledTimes(1);
        const [finalState] = onEnd.mock.calls[0] as [DragState, PointerEvent];
        expect(finalState.dragging).toBe(false);
    });

    it('does not call onStart when disabled=true', () => {
        const onStart = vi.fn();
        render(<DragHandle onStart={onStart} disabled={true} />);
        const el = screen.getByTestId('handle');
        fireEvent.pointerDown(el, { button: 0, clientX: 10, clientY: 10 });
        expect(onStart).not.toHaveBeenCalled();
    });

    it('ignores non-primary button presses (button !== 0)', () => {
        const onStart = vi.fn();
        render(<DragHandle onStart={onStart} />);
        const el = screen.getByTestId('handle');
        fireEvent.pointerDown(el, { button: 2, clientX: 10, clientY: 10 });
        expect(onStart).not.toHaveBeenCalled();
    });

    it('does not start drag on data-no-drag children', () => {
        const onStart = vi.fn();
        function NoDragHost(): ReactElement {
            const { onPointerDown } = useDraggable({ onStart });
            return (
                <div data-testid="wrap" onPointerDown={onPointerDown}>
                    <button data-no-drag>no drag</button>
                </div>
            );
        }
        const { container } = render(<NoDragHost />);
        const btn = container.querySelector('[data-no-drag]') as HTMLElement;
        fireEvent.pointerDown(btn, { button: 0 });
        expect(onStart).not.toHaveBeenCalled();
    });

    it('dragging state is true after pointerdown and false after pointerup', () => {
        function StatefulHandle(): ReactElement {
            const { onPointerDown, dragging } = useDraggable({});
            return (
                <div
                    data-testid="sh"
                    data-dragging={String(dragging)}
                    onPointerDown={onPointerDown}
                />
            );
        }
        render(<StatefulHandle />);
        const el = screen.getByTestId('sh');
        expect(el.getAttribute('data-dragging')).toBe('false');
        fireEvent.pointerDown(el, { button: 0, clientX: 0, clientY: 0 });
        expect(el.getAttribute('data-dragging')).toBe('true');
        act(() => {
            windowPointerEvent('pointerup', { clientX: 10, clientY: 10 });
        });
        expect(el.getAttribute('data-dragging')).toBe('false');
    });

    it('accumulates multiple move events correctly', () => {
        const moves: number[] = [];
        const onMove = (s: DragState): void => {
            moves.push(s.dx);
        };
        render(<DragHandle onMove={onMove} />);
        const el = screen.getByTestId('handle');
        fireEvent.pointerDown(el, { button: 0, clientX: 0, clientY: 0 });
        windowPointerEvent('pointermove', { clientX: 10, clientY: 0 });
        windowPointerEvent('pointermove', { clientX: 25, clientY: 0 });
        windowPointerEvent('pointermove', { clientX: 40, clientY: 0 });
        expect(moves).toEqual([10, 25, 40]);
    });
});

// Workaround: the last test uses useDraggable inline which needs a component wrapper.
// We do it correctly here by wrapping in a React component.
describe('useDraggable — data-no-drag via React component', () => {
    it('does not call onStart when clicking data-no-drag child', () => {
        const onStart = vi.fn();
        function Host(): ReactElement {
            const { onPointerDown } = useDraggable({ onStart });
            return (
                <div onPointerDown={onPointerDown} data-testid="host">
                    <button data-no-drag data-testid="no-drag-btn">
                        stop
                    </button>
                </div>
            );
        }
        render(<Host />);
        const btn = screen.getByTestId('no-drag-btn');
        fireEvent.pointerDown(btn, { button: 0, clientX: 0, clientY: 0 });
        expect(onStart).not.toHaveBeenCalled();
    });
});
