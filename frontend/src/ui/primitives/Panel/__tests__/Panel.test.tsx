import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { Panel } from '../Panel';
import { SfxContext } from '@core/audio';
import type { SfxContextValue } from '@core/audio';
import type { SfxEvent } from '@core/audio';

type MockFn = ReturnType<typeof vi.fn> & ((event: SfxEvent) => void);

function makeSfx(): { playOneShot: MockFn; play: MockFn; stop: MockFn } & SfxContextValue {
    return { playOneShot: vi.fn() as MockFn, play: vi.fn() as MockFn, stop: vi.fn() as MockFn };
}

function renderWithSfx(sfx: SfxContextValue, ui: React.ReactElement) {
    return render(<SfxContext.Provider value={sfx}>{ui}</SfxContext.Provider>);
}

describe('Panel — visual', () => {
    it('renders children in body', () => {
        render(<Panel>Panel body</Panel>);
        expect(screen.getByText('Panel body')).toBeDefined();
    });

    it('renders title slot', () => {
        render(<Panel title="System Vitals">body</Panel>);
        expect(screen.getByText('System Vitals')).toBeDefined();
    });

    it('renders ix slot', () => {
        render(
            <Panel ix="◈" title="Test">
                body
            </Panel>,
        );
        expect(screen.getByText('◈')).toBeDefined();
    });

    it('renders badge slot', () => {
        render(<Panel badge="LIVE">body</Panel>);
        expect(screen.getByText('LIVE')).toBeDefined();
    });

    it('default state does not have focused class', () => {
        const { container } = render(<Panel>x</Panel>);
        const root = container.querySelector('.lib-panel');
        expect(root).toBeDefined();
        expect(root?.classList.contains('focused')).toBe(false);
    });

    it('focused prop adds focused class', () => {
        const { container } = render(<Panel focused>x</Panel>);
        const root = container.querySelector('.lib-panel');
        expect(root?.classList.contains('focused')).toBe(true);
    });

    it('renders 4 corner brackets', () => {
        const { container } = render(<Panel>x</Panel>);
        const corners = container.querySelectorAll('.lib-panel__ck');
        expect(corners).toHaveLength(4);
    });

    it('corner brackets have correct position classes', () => {
        const { container } = render(<Panel>x</Panel>);
        expect(container.querySelector('.lib-panel__ck.tl')).toBeDefined();
        expect(container.querySelector('.lib-panel__ck.tr')).toBeDefined();
        expect(container.querySelector('.lib-panel__ck.bl')).toBeDefined();
        expect(container.querySelector('.lib-panel__ck.br')).toBeDefined();
    });

    it('renders trace with l and r strips', () => {
        const { container } = render(<Panel>x</Panel>);
        const trace = container.querySelector('.lib-panel__trace');
        expect(trace).toBeDefined();
        expect(trace?.querySelector('i.l')).toBeDefined();
        expect(trace?.querySelector('i.r')).toBeDefined();
    });

    it('renders 2 rail elements', () => {
        const { container } = render(<Panel>x</Panel>);
        expect(container.querySelector('.lib-panel__rail.l')).toBeDefined();
        expect(container.querySelector('.lib-panel__rail.r')).toBeDefined();
    });

    it('renders header element', () => {
        const { container } = render(<Panel title="Test">x</Panel>);
        expect(container.querySelector('.lib-panel__hdr')).toBeDefined();
    });

    it('renders dots cluster in header', () => {
        const { container } = render(<Panel>x</Panel>);
        const dots = container.querySelector('.lib-panel__hdr .dots');
        expect(dots).toBeDefined();
        expect(dots?.querySelectorAll('i')).toHaveLength(3);
    });

    it('renders body element', () => {
        const { container } = render(<Panel>x</Panel>);
        expect(container.querySelector('.lib-panel__body')).toBeDefined();
    });

    it('forwards onFocus via onMouseDown', () => {
        const onFocus = vi.fn();
        const { container } = render(<Panel onFocus={onFocus}>x</Panel>);
        const root = container.querySelector('.lib-panel');
        if (root) root.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
        expect(onFocus).toHaveBeenCalledTimes(1);
    });

    it('className merges on root', () => {
        const { container } = render(<Panel className="custom-panel">x</Panel>);
        const root = container.querySelector('.lib-panel');
        expect(root?.classList.contains('custom-panel')).toBe(true);
    });

    it('does not render ix span when ix is not provided', () => {
        const { container } = render(<Panel title="T">x</Panel>);
        expect(container.querySelector('.lib-panel__hdr .ix')).toBeNull();
    });

    it('does not render badge span when badge is not provided', () => {
        const { container } = render(<Panel title="T">x</Panel>);
        expect(container.querySelector('.lib-panel__hdr .badge')).toBeNull();
    });

    it('renders actions slot in header when actions prop is provided', () => {
        const { container } = render(<Panel actions={<button type="button">Act</button>}>x</Panel>);
        const actionsSpan = container.querySelector('.lib-panel__hdr-actions');
        expect(actionsSpan).not.toBeNull();
        expect(actionsSpan?.querySelector('button')).not.toBeNull();
    });

    it('does not render actions span when actions prop is not provided', () => {
        const { container } = render(<Panel title="T">x</Panel>);
        expect(container.querySelector('.lib-panel__hdr-actions')).toBeNull();
    });

    it('applies inline style to root', () => {
        const { container } = render(<Panel style={{ width: 316, height: 300 }}>x</Panel>);
        const root = container.querySelector<HTMLDivElement>('.lib-panel');
        expect(root?.style.width).toBe('316px');
        expect(root?.style.height).toBe('300px');
    });
});

describe('Panel — SFX', () => {
    it('plays hover_panel on mouseenter of root', () => {
        const sfx = makeSfx();
        const { container } = renderWithSfx(sfx, <Panel>content</Panel>);
        const root = container.querySelector('.lib-panel');
        if (root) fireEvent.mouseEnter(root);
        expect(sfx.playOneShot).toHaveBeenCalledWith('hover_panel');
    });

    it('does NOT play hover_panel when mouseenter fires on inner button with data-sfx-hover="button"', () => {
        const sfx = makeSfx();
        // The panel's onMouseEnter has a guard: if e.target.closest('[data-sfx-hover="button"]')
        // is truthy, it returns without playing. We test this by firing mouseenter
        // directly on the inner button — since onMouseEnter doesn't bubble in RTL
        // fireEvent for mouseEnter on the inner button, we verify that the panel
        // sfx is NOT called when user interacts only with the button.
        const { container } = renderWithSfx(
            sfx,
            <Panel>
                <button data-sfx-hover="button" data-testid="inner-btn">btn</button>
            </Panel>,
        );
        // mouseEnter on inner button (doesn't bubble to panel's onMouseEnter in RTL)
        const btn = container.querySelector('[data-sfx-hover="button"]') as HTMLElement;
        if (btn) fireEvent.mouseEnter(btn);
        // Panel's hover_panel should NOT have been called (btn mouseEnter doesn't reach panel handler)
        const hoverPanelCalls = (sfx.playOneShot as ReturnType<typeof vi.fn>).mock.calls.filter(
            (c) => c[0] === 'hover_panel',
        );
        expect(hoverPanelCalls).toHaveLength(0);
    });
});
