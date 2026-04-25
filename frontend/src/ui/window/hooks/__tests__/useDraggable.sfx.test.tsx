/**
 * useDraggable — SFX integration tests (Vitest + RTL).
 *
 * Verifies:
 *   - drag_start one-shot fires on drag begin
 *   - drag_move loop starts on drag begin
 *   - drag_move loop stops on drag end
 *   - drag_end one-shot fires on drag end
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { type ReactElement } from 'react';
import { useDraggable } from '../useDraggable';
import { SfxContext } from '@core/audio';
import type { SfxContextValue } from '@core/audio';
import type { SfxEvent } from '@core/audio';

type MockFn = ReturnType<typeof vi.fn> & ((event: SfxEvent) => void);

function makeSfx(): { playOneShot: MockFn; play: MockFn; stop: MockFn } & SfxContextValue {
    return {
        playOneShot: vi.fn() as MockFn,
        play: vi.fn() as MockFn,
        stop: vi.fn() as MockFn,
    };
}

function DragHandle(): ReactElement {
    const { onPointerDown } = useDraggable({});
    return <div data-testid="handle" onPointerDown={onPointerDown}>drag</div>;
}

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

describe('useDraggable — SFX', () => {
    it('plays drag_start one-shot on drag begin', () => {
        const sfx = makeSfx();
        render(
            <SfxContext.Provider value={sfx}>
                <DragHandle />
            </SfxContext.Provider>,
        );
        fireEvent.pointerDown(screen.getByTestId('handle'), { button: 0, clientX: 0, clientY: 0 });
        expect(sfx.playOneShot).toHaveBeenCalledWith('drag_start');
    });

    it('starts drag_move loop on drag begin', () => {
        const sfx = makeSfx();
        render(
            <SfxContext.Provider value={sfx}>
                <DragHandle />
            </SfxContext.Provider>,
        );
        fireEvent.pointerDown(screen.getByTestId('handle'), { button: 0, clientX: 0, clientY: 0 });
        expect(sfx.play).toHaveBeenCalledWith('drag_move');
    });

    it('stops drag_move loop on drag end', () => {
        const sfx = makeSfx();
        render(
            <SfxContext.Provider value={sfx}>
                <DragHandle />
            </SfxContext.Provider>,
        );
        fireEvent.pointerDown(screen.getByTestId('handle'), { button: 0, clientX: 0, clientY: 0 });
        act(() => {
            windowPointerEvent('pointerup', { clientX: 10, clientY: 10 });
        });
        expect(sfx.stop).toHaveBeenCalledWith('drag_move');
    });

    it('plays drag_end one-shot on drag end', () => {
        const sfx = makeSfx();
        render(
            <SfxContext.Provider value={sfx}>
                <DragHandle />
            </SfxContext.Provider>,
        );
        fireEvent.pointerDown(screen.getByTestId('handle'), { button: 0, clientX: 0, clientY: 0 });
        act(() => {
            windowPointerEvent('pointerup', { clientX: 10, clientY: 10 });
        });
        expect(sfx.playOneShot).toHaveBeenCalledWith('drag_end');
    });

    it('does not fire SFX when disabled', () => {
        const sfx = makeSfx();
        function DisabledHandle(): ReactElement {
            const { onPointerDown } = useDraggable({ disabled: true });
            return <div data-testid="handle" onPointerDown={onPointerDown}>drag</div>;
        }
        render(
            <SfxContext.Provider value={sfx}>
                <DisabledHandle />
            </SfxContext.Provider>,
        );
        fireEvent.pointerDown(screen.getByTestId('handle'), { button: 0, clientX: 0, clientY: 0 });
        expect(sfx.playOneShot).not.toHaveBeenCalledWith('drag_start');
        expect(sfx.play).not.toHaveBeenCalledWith('drag_move');
    });
});
