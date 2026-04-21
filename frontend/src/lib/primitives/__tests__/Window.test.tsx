/**
 * Window lib primitive — SFX integration tests (Vitest + RTL).
 *
 * Verifies:
 *   - hover_panel does NOT fire directly from Window root (Panel owns that)
 *   - Reset button click → click + recall
 *   - ModeToggle button click (compact) → click + expand
 *   - ModeToggle button click (expanded) → click + collapse
 *   - Close button click → click
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { Window } from '../Window';
import { SfxContext } from '../../audio/SfxContext';
import type { SfxContextValue } from '../../audio/SfxContext';
import type { SfxEvent } from '../../audio/config';

type MockFn = ReturnType<typeof vi.fn> & ((event: SfxEvent) => void);

function makeSfx(): { playOneShot: MockFn; play: MockFn; stop: MockFn } & SfxContextValue {
    return { playOneShot: vi.fn() as MockFn, play: vi.fn() as MockFn, stop: vi.fn() as MockFn };
}

const defaultPosition = { x: 0, y: 0, w: 400, h: 300 };

function renderWindow(
    sfx: SfxContextValue,
    props: Partial<React.ComponentProps<typeof Window>> = {},
) {
    const mergedProps = {
        id: 'test-win',
        position: defaultPosition,
        itemRenderer: () => <div>content</div>,
        ...props,
    };
    return render(
        <SfxContext.Provider value={sfx}>
            <Window {...mergedProps} />
        </SfxContext.Provider>,
    );
}

beforeEach(() => {
    HTMLElement.prototype.setPointerCapture = vi.fn();
    HTMLElement.prototype.releasePointerCapture = vi.fn();
});

describe('Window — SFX', () => {
    it('does NOT fire hover_panel directly from Window root mouseenter (Panel owns that)', () => {
        const sfx = makeSfx();
        const { container } = renderWindow(sfx);
        const root = container.querySelector('.lib-window');
        if (root) fireEvent.mouseEnter(root);
        const hoverPanelCalls = (sfx.playOneShot as ReturnType<typeof vi.fn>).mock.calls.filter(
            (c) => c[0] === 'hover_panel',
        );
        // Window root has no onMouseEnter for hover_panel — Panel's handler owns it.
        // fireEvent.mouseEnter on the Window root div does not propagate into Panel's handler,
        // so no hover_panel call should originate from this event.
        expect(hoverPanelCalls).toHaveLength(0);
    });

    it('Reset button click fires click + recall', () => {
        const sfx = makeSfx();
        const onReset = vi.fn();
        renderWindow(sfx, { onReset });
        const resetBtn = screen.getByRole('button', { name: /reset window/i });
        fireEvent.click(resetBtn);
        expect(sfx.playOneShot).toHaveBeenCalledWith('click');
        expect(sfx.playOneShot).toHaveBeenCalledWith('recall');
    });

    it('ModeToggle click in compact mode fires click + expand', () => {
        const sfx = makeSfx();
        const onModeToggle = vi.fn();
        renderWindow(sfx, { onModeToggle, mode: 'compact' });
        const modeBtn = screen.getByRole('button', { name: /undock window/i });
        fireEvent.click(modeBtn);
        expect(sfx.playOneShot).toHaveBeenCalledWith('click');
        expect(sfx.playOneShot).toHaveBeenCalledWith('expand');
    });

    it('ModeToggle click in expanded mode fires click + collapse', () => {
        const sfx = makeSfx();
        const onModeToggle = vi.fn();
        renderWindow(sfx, { onModeToggle, mode: 'expanded' });
        const modeBtn = screen.getByRole('button', { name: /dock window/i });
        fireEvent.click(modeBtn);
        expect(sfx.playOneShot).toHaveBeenCalledWith('click');
        expect(sfx.playOneShot).toHaveBeenCalledWith('collapse');
    });

    it('Close button click fires click', () => {
        const sfx = makeSfx();
        const onClose = vi.fn();
        renderWindow(sfx, { onClose });
        const closeBtn = screen.getByRole('button', { name: /close window/i });
        fireEvent.click(closeBtn);
        expect(sfx.playOneShot).toHaveBeenCalledWith('click');
    });

    it('header buttons have data-sfx-hover="button"', () => {
        const sfx = makeSfx();
        const onClose = vi.fn();
        const onReset = vi.fn();
        const onModeToggle = vi.fn();
        const { container } = renderWindow(sfx, { onClose, onReset, onModeToggle, mode: 'compact' });
        const sfxButtons = container.querySelectorAll('.lib-window__btn[data-sfx-hover="button"]');
        expect(sfxButtons.length).toBeGreaterThanOrEqual(3);
    });
});

describe('Window — visual', () => {
    it('renders with data-window-id', () => {
        const { container } = renderWindow(makeSfx());
        expect(container.querySelector('[data-window-id="test-win"]')).not.toBeNull();
    });

    it('renders resize handles when resizable=true', () => {
        const { container } = renderWindow(makeSfx(), { resizable: true });
        expect(container.querySelector('[data-testid="resize-se"]')).not.toBeNull();
    });

    it('does not render resize handles when resizable=false', () => {
        const { container } = renderWindow(makeSfx(), { resizable: false });
        expect(container.querySelector('[data-testid="resize-se"]')).toBeNull();
    });

    it('renders drag handle', () => {
        renderWindow(makeSfx());
        expect(screen.getByTestId('window-drag-handle')).toBeDefined();
    });

    it('renders close button when onClose is provided', () => {
        renderWindow(makeSfx(), { onClose: vi.fn() });
        expect(screen.getByRole('button', { name: /close window/i })).toBeDefined();
    });

    it('does not render close button when onClose is not provided', () => {
        renderWindow(makeSfx());
        expect(screen.queryByRole('button', { name: /close window/i })).toBeNull();
    });
});
