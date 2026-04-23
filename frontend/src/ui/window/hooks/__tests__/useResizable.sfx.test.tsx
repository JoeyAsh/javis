/**
 * useResizable — SFX integration tests (Vitest + RTL).
 *
 * Verifies:
 *   - resize loop starts on resize begin
 *   - resize loop stops on resize end
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { type ReactElement } from 'react';
import { useResizable } from '../useResizable';
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

function ResizeHandle(): ReactElement {
    const { onPointerDown } = useResizable({});
    return <span data-testid="handle" onPointerDown={onPointerDown('se')} />;
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

describe('useResizable — SFX', () => {
    it('starts resize loop on resize begin', () => {
        const sfx = makeSfx();
        render(
            <SfxContext.Provider value={sfx}>
                <ResizeHandle />
            </SfxContext.Provider>,
        );
        fireEvent.pointerDown(screen.getByTestId('handle'), { button: 0, clientX: 0, clientY: 0 });
        expect(sfx.play).toHaveBeenCalledWith('resize');
    });

    it('stops resize loop on resize end', () => {
        const sfx = makeSfx();
        render(
            <SfxContext.Provider value={sfx}>
                <ResizeHandle />
            </SfxContext.Provider>,
        );
        fireEvent.pointerDown(screen.getByTestId('handle'), { button: 0, clientX: 0, clientY: 0 });
        act(() => {
            windowPointerEvent('pointerup', { clientX: 30, clientY: 30 });
        });
        expect(sfx.stop).toHaveBeenCalledWith('resize');
    });

    it('does not fire SFX when disabled', () => {
        const sfx = makeSfx();
        function DisabledHandle(): ReactElement {
            const { onPointerDown } = useResizable({ disabled: true });
            return <span data-testid="handle" onPointerDown={onPointerDown('se')} />;
        }
        render(
            <SfxContext.Provider value={sfx}>
                <DisabledHandle />
            </SfxContext.Provider>,
        );
        fireEvent.pointerDown(screen.getByTestId('handle'), { button: 0, clientX: 0, clientY: 0 });
        expect(sfx.play).not.toHaveBeenCalledWith('resize');
    });
});
