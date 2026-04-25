import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { type ReactElement } from 'react';
import { useResizable } from '../useResizable';
import type { ResizeDir, ResizeState } from '../useResizable';

/** Simple test component wiring useResizable to a single handle div. */
function ResizeHandle({
    dir,
    onStart,
    onMove,
    onEnd,
    disabled,
}: {
    dir: ResizeDir;
    onStart?: (d: ResizeDir, e: PointerEvent) => void;
    onMove?: (state: ResizeState, e: PointerEvent) => void;
    onEnd?: (state: ResizeState, e: PointerEvent) => void;
    disabled?: boolean;
}): ReactElement {
    const {
        onPointerDown,
        resizing,
        dir: activeDir,
    } = useResizable({
        onStart,
        onMove,
        onEnd,
        disabled,
    });
    return (
        <span
            data-testid="handle"
            data-resizing={resizing ? 'true' : 'false'}
            data-dir={activeDir ?? 'null'}
            onPointerDown={onPointerDown(dir)}
        />
    );
}

/** Fire a native PointerEvent on window. */
function windowPointerEvent(type: string, init?: PointerEventInit): void {
    window.dispatchEvent(new PointerEvent(type, { bubbles: true, ...init }));
}

beforeEach(() => {
    HTMLElement.prototype.setPointerCapture = vi.fn();
    HTMLElement.prototype.releasePointerCapture = vi.fn();
});

afterEach(() => {
    vi.restoreAllMocks();
});

describe('useResizable', () => {
    it('renders without resizing by default', () => {
        render(<ResizeHandle dir="se" />);
        expect(screen.getByTestId('handle').getAttribute('data-resizing')).toBe('false');
        expect(screen.getByTestId('handle').getAttribute('data-dir')).toBe('null');
    });

    it('calls onStart with correct dir when pointerdown fires', () => {
        const onStart = vi.fn();
        render(<ResizeHandle dir="se" onStart={onStart} />);
        fireEvent.pointerDown(screen.getByTestId('handle'), {
            button: 0,
            clientX: 100,
            clientY: 200,
        });
        expect(onStart).toHaveBeenCalledOnce();
        expect(onStart.mock.calls[0][0]).toBe('se');
        expect(onStart.mock.calls[0][1]).toBeInstanceOf(PointerEvent);
    });

    it('calls onStart with correct dir for each direction', () => {
        const dirs: ResizeDir[] = ['n', 's', 'e', 'w', 'ne', 'nw', 'se', 'sw'];
        for (const dir of dirs) {
            const onStart = vi.fn();
            const { unmount } = render(<ResizeHandle dir={dir} onStart={onStart} />);
            fireEvent.pointerDown(screen.getByTestId('handle'), {
                button: 0,
                clientX: 50,
                clientY: 50,
            });
            expect(onStart.mock.calls[0][0]).toBe(dir);
            unmount();
        }
    });

    it('calls onMove with correct dx/dy during pointermove', () => {
        const onMove = vi.fn();
        render(<ResizeHandle dir="se" onMove={onMove} />);
        fireEvent.pointerDown(screen.getByTestId('handle'), {
            button: 0,
            clientX: 100,
            clientY: 200,
        });
        act(() => {
            windowPointerEvent('pointermove', { clientX: 130, clientY: 250 });
        });
        expect(onMove).toHaveBeenCalledOnce();
        const [state] = onMove.mock.calls[0] as [ResizeState, PointerEvent];
        expect(state.resizing).toBe(true);
        expect(state.dir).toBe('se');
        expect(state.dx).toBe(30);
        expect(state.dy).toBe(50);
    });

    it('calls onEnd and clears state when pointerup fires', () => {
        const onEnd = vi.fn();
        render(<ResizeHandle dir="nw" onEnd={onEnd} />);
        const handle = screen.getByTestId('handle');

        fireEvent.pointerDown(handle, { button: 0, clientX: 50, clientY: 50 });
        expect(handle.getAttribute('data-resizing')).toBe('true');
        expect(handle.getAttribute('data-dir')).toBe('nw');

        act(() => {
            windowPointerEvent('pointerup', { clientX: 60, clientY: 60 });
        });

        expect(onEnd).toHaveBeenCalledOnce();
        const [finalState] = onEnd.mock.calls[0] as [ResizeState, PointerEvent];
        expect(finalState.resizing).toBe(false);

        expect(handle.getAttribute('data-resizing')).toBe('false');
        expect(handle.getAttribute('data-dir')).toBe('null');
    });

    it('does not call onStart when disabled=true', () => {
        const onStart = vi.fn();
        render(<ResizeHandle dir="se" onStart={onStart} disabled={true} />);
        fireEvent.pointerDown(screen.getByTestId('handle'), { button: 0 });
        expect(onStart).not.toHaveBeenCalled();
    });

    it('ignores non-primary button presses (button !== 0)', () => {
        const onStart = vi.fn();
        render(<ResizeHandle dir="se" onStart={onStart} />);
        fireEvent.pointerDown(screen.getByTestId('handle'), { button: 2 });
        expect(onStart).not.toHaveBeenCalled();
    });

    it('accumulates multiple move events correctly', () => {
        const dxValues: number[] = [];
        const onMove = (s: ResizeState): void => {
            dxValues.push(s.dx);
        };
        render(<ResizeHandle dir="e" onMove={onMove} />);
        fireEvent.pointerDown(screen.getByTestId('handle'), {
            button: 0,
            clientX: 0,
            clientY: 0,
        });
        windowPointerEvent('pointermove', { clientX: 10, clientY: 0 });
        windowPointerEvent('pointermove', { clientX: 25, clientY: 0 });
        windowPointerEvent('pointermove', { clientX: 40, clientY: 0 });
        expect(dxValues).toEqual([10, 25, 40]);
    });

    it('cleans up window listeners after pointerup', () => {
        const onMove = vi.fn();
        render(<ResizeHandle dir="s" onMove={onMove} />);
        fireEvent.pointerDown(screen.getByTestId('handle'), {
            button: 0,
            clientX: 0,
            clientY: 0,
        });
        act(() => {
            windowPointerEvent('pointerup', {});
        });
        // Further move events should not call onMove
        act(() => {
            windowPointerEvent('pointermove', { clientX: 50, clientY: 50 });
        });
        // onMove should have been called 0 times (no move before up)
        expect(onMove).not.toHaveBeenCalled();
    });
});
