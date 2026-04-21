import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { Window } from '../Window';
import type { WindowState } from '../Window';

const BASE_POS = { x: 10, y: 20, w: 300, h: 200 };

beforeEach(() => {
    HTMLElement.prototype.setPointerCapture = vi.fn();
    HTMLElement.prototype.releasePointerCapture = vi.fn();
});

afterEach(() => {
    vi.restoreAllMocks();
});

describe('Window', () => {
    it('renders without crashing', () => {
        const { container } = render(
            <Window id="w1" position={BASE_POS}>
                body
            </Window>,
        );
        expect(container.querySelector('.lib-window')).toBeDefined();
    });

    it('renders title in Panel chrome', () => {
        render(
            <Window id="w1" title="My Window" position={BASE_POS}>
                body
            </Window>,
        );
        expect(screen.getByText('My Window')).toBeDefined();
    });

    it('renders ix slot', () => {
        render(
            <Window id="w1" ix="◈" position={BASE_POS}>
                body
            </Window>,
        );
        expect(screen.getByText('◈')).toBeDefined();
    });

    it('renders badge slot when no action buttons are provided', () => {
        render(
            <Window id="w1" badge="LIVE" position={BASE_POS}>
                body
            </Window>,
        );
        expect(screen.getByText('LIVE')).toBeDefined();
    });

    it('renders Panel corner brackets (chrome present)', () => {
        const { container } = render(
            <Window id="w1" position={BASE_POS}>
                body
            </Window>,
        );
        expect(container.querySelectorAll('.lib-panel__ck')).toHaveLength(4);
    });
});

describe('Window — data-state attribute', () => {
    const states: WindowState[] = [
        'idle',
        'dragging',
        'snap-preview',
        'swap-preview',
        'settling',
        'focused',
        'minimized',
        'maximized',
    ];

    for (const s of states) {
        it(`data-state="${s}" when state="${s}"`, () => {
            const { container } = render(
                <Window id="w1" position={BASE_POS} state={s}>
                    body
                </Window>,
            );
            const root = container.querySelector('.lib-window');
            expect(root?.getAttribute('data-state')).toBe(s);
        });
    }
});

describe('Window — focused prop', () => {
    it('focused prop adds focused class to inner Panel', () => {
        const { container } = render(
            <Window id="w1" position={BASE_POS} focused>
                body
            </Window>,
        );
        expect(container.querySelector('.lib-panel')?.classList.contains('focused')).toBe(true);
    });

    it('no focused class by default', () => {
        const { container } = render(
            <Window id="w1" position={BASE_POS}>
                body
            </Window>,
        );
        expect(container.querySelector('.lib-panel')?.classList.contains('focused')).toBe(false);
    });
});

describe('Window — drag callbacks', () => {
    it('fires onDragStart when header is pointer-downed', () => {
        const onDragStart = vi.fn();
        const { container } = render(
            <Window id="win-1" position={BASE_POS} onDragStart={onDragStart}>
                body
            </Window>,
        );
        const handle = container.querySelector('[data-testid="window-drag-handle"]') as HTMLElement;
        fireEvent.pointerDown(handle, { button: 0, clientX: 50, clientY: 50 });
        expect(onDragStart).toHaveBeenCalledOnce();
        expect(onDragStart.mock.calls[0][0]).toBe('win-1');
    });

    it('fires onDragMove when pointer moves after pointerdown', () => {
        const onDragMove = vi.fn();
        const { container } = render(
            <Window id="win-1" position={BASE_POS} onDragMove={onDragMove}>
                body
            </Window>,
        );
        const handle = container.querySelector('[data-testid="window-drag-handle"]') as HTMLElement;
        fireEvent.pointerDown(handle, { button: 0, clientX: 0, clientY: 0 });
        act(() => {
            window.dispatchEvent(
                new PointerEvent('pointermove', { bubbles: true, clientX: 20, clientY: 30 }),
            );
        });
        expect(onDragMove).toHaveBeenCalled();
        const [id, dx, dy] = onDragMove.mock.calls[0] as [string, number, number];
        expect(id).toBe('win-1');
        expect(dx).toBe(20);
        expect(dy).toBe(30);
    });

    it('fires onDragEnd when pointer released', () => {
        const onDragEnd = vi.fn();
        const { container } = render(
            <Window id="win-1" position={BASE_POS} onDragEnd={onDragEnd}>
                body
            </Window>,
        );
        const handle = container.querySelector('[data-testid="window-drag-handle"]') as HTMLElement;
        fireEvent.pointerDown(handle, { button: 0, clientX: 0, clientY: 0 });
        act(() => {
            window.dispatchEvent(new PointerEvent('pointerup', { bubbles: true }));
        });
        expect(onDragEnd).toHaveBeenCalledOnce();
        expect(onDragEnd.mock.calls[0][0]).toBe('win-1');
    });

    it('draggable=false disables drag callbacks', () => {
        const onDragStart = vi.fn();
        const { container } = render(
            <Window id="win-1" position={BASE_POS} draggable={false} onDragStart={onDragStart}>
                body
            </Window>,
        );
        const handle = container.querySelector('[data-testid="window-drag-handle"]') as HTMLElement;
        fireEvent.pointerDown(handle, { button: 0, clientX: 0, clientY: 0 });
        expect(onDragStart).not.toHaveBeenCalled();
    });
});

describe('Window — action buttons', () => {
    it('renders minimize button when onMinimize is provided', () => {
        render(
            <Window id="w1" position={BASE_POS} onMinimize={vi.fn()}>
                body
            </Window>,
        );
        expect(screen.getByRole('button', { name: /minimize/i })).toBeDefined();
    });

    it('fires onMinimize with window id when minimize button is clicked', () => {
        const onMinimize = vi.fn();
        render(
            <Window id="w1" position={BASE_POS} onMinimize={onMinimize}>
                body
            </Window>,
        );
        fireEvent.click(screen.getByRole('button', { name: /minimize/i }));
        expect(onMinimize).toHaveBeenCalledWith('w1');
    });

    it('renders maximize button when onMaximize is provided', () => {
        render(
            <Window id="w1" position={BASE_POS} onMaximize={vi.fn()}>
                body
            </Window>,
        );
        expect(screen.getByRole('button', { name: /maximize/i })).toBeDefined();
    });

    it('fires onMaximize with window id when maximize button is clicked', () => {
        const onMaximize = vi.fn();
        render(
            <Window id="w1" position={BASE_POS} onMaximize={onMaximize}>
                body
            </Window>,
        );
        fireEvent.click(screen.getByRole('button', { name: /maximize/i }));
        expect(onMaximize).toHaveBeenCalledWith('w1');
    });

    it('renders close button when onClose is provided', () => {
        render(
            <Window id="w1" position={BASE_POS} onClose={vi.fn()}>
                body
            </Window>,
        );
        expect(screen.getByRole('button', { name: /close/i })).toBeDefined();
    });

    it('fires onClose with window id when close button is clicked', () => {
        const onClose = vi.fn();
        render(
            <Window id="w1" position={BASE_POS} onClose={onClose}>
                body
            </Window>,
        );
        fireEvent.click(screen.getByRole('button', { name: /close/i }));
        expect(onClose).toHaveBeenCalledWith('w1');
    });

    it('does not render action buttons when none are provided', () => {
        render(
            <Window id="w1" position={BASE_POS}>
                body
            </Window>,
        );
        expect(screen.queryByRole('button', { name: /minimize/i })).toBeNull();
        expect(screen.queryByRole('button', { name: /maximize/i })).toBeNull();
        expect(screen.queryByRole('button', { name: /close/i })).toBeNull();
    });
});

describe('Window — className', () => {
    it('merges className without replacing base class', () => {
        const { container } = render(
            <Window id="w1" position={BASE_POS} className="custom-win">
                body
            </Window>,
        );
        const root = container.querySelector('.lib-window');
        expect(root?.classList.contains('custom-win')).toBe(true);
        expect(root?.classList.contains('lib-window')).toBe(true);
    });
});
