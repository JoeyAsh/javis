/**
 * HudButton — Vitest + RTL tests.
 *
 * Tests cover:
 *   - Click fires playOneShot('click') via SfxContext
 *   - mouseenter held ≥ 200 ms fires playOneShot('hover') exactly once
 *   - mouseenter then mouseleave before 200 ms → hover NOT played
 *   - Rapid repeated enters within 200 ms on same element → at most 1 hover
 *   - Two buttons side-by-side: each fires its own hover when stable
 *   - disabled → no click SFX, no hover SFX, no onClick called
 *   - onClick prop is called when not disabled
 */

import { render, screen, fireEvent } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { HudButton } from '../HudButton';
import { SfxProvider } from '../../../../lib/audio/SfxContext';
import type { ReactNode } from 'react';

// ---------------------------------------------------------------------------
// Fake timers
// ---------------------------------------------------------------------------

beforeEach(() => {
    vi.useFakeTimers();
});

afterEach(() => {
    vi.runAllTimers();
    vi.useRealTimers();
    vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// SfxContext mock
// ---------------------------------------------------------------------------

const mockPlayOneShot = vi.fn();

const mockPlay = vi.fn();
const mockStop = vi.fn();

function Wrapper({ children }: { children: ReactNode }) {
    return (
        <SfxProvider playOneShot={mockPlayOneShot} play={mockPlay} stop={mockStop}>
            {children}
        </SfxProvider>
    );
}

function renderButton(props: Partial<React.ComponentProps<typeof HudButton>> = {}) {
    return render(<HudButton {...props}>{props.children ?? 'Click me'}</HudButton>, {
        wrapper: Wrapper,
    });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('HudButton — click SFX', () => {
    it('click fires playOneShot("click") via SfxContext', () => {
        renderButton();
        fireEvent.click(screen.getByRole('button'));
        expect(mockPlayOneShot).toHaveBeenCalledWith('click');
    });

    it('click calls onClick prop', () => {
        const onClick = vi.fn();
        renderButton({ onClick });
        fireEvent.click(screen.getByRole('button'));
        expect(onClick).toHaveBeenCalledTimes(1);
    });

    it('each click fires one click SFX', () => {
        renderButton();
        const btn = screen.getByRole('button');
        fireEvent.click(btn);
        fireEvent.click(btn);
        const clickCalls = (mockPlayOneShot as ReturnType<typeof vi.fn>).mock.calls.filter(
            (c) => c[0] === 'click',
        );
        expect(clickCalls).toHaveLength(2);
    });
});

describe('HudButton — hover SFX debounce', () => {
    it('mouseenter held ≥ 200 ms fires playOneShot("hover_button") exactly once', () => {
        renderButton();
        fireEvent.mouseEnter(screen.getByRole('button'));
        vi.advanceTimersByTime(200);
        const hoverCalls = (mockPlayOneShot as ReturnType<typeof vi.fn>).mock.calls.filter(
            (c) => c[0] === 'hover_button',
        );
        expect(hoverCalls).toHaveLength(1);
    });

    it('mouseenter then mouseleave before 200 ms → hover_button NOT played', () => {
        renderButton();
        const btn = screen.getByRole('button');
        fireEvent.mouseEnter(btn);
        vi.advanceTimersByTime(100);
        fireEvent.mouseLeave(btn);
        vi.advanceTimersByTime(200);
        const hoverCalls = (mockPlayOneShot as ReturnType<typeof vi.fn>).mock.calls.filter(
            (c) => c[0] === 'hover_button',
        );
        expect(hoverCalls).toHaveLength(0);
    });

    it('rapid repeated mouseenter within 200 ms fires at most 1 hover_button', () => {
        renderButton();
        const btn = screen.getByRole('button');
        fireEvent.mouseEnter(btn);
        vi.advanceTimersByTime(50);
        fireEvent.mouseLeave(btn);
        fireEvent.mouseEnter(btn);
        vi.advanceTimersByTime(50);
        fireEvent.mouseLeave(btn);
        fireEvent.mouseEnter(btn);
        vi.advanceTimersByTime(200); // let the final timer fire
        const hoverCalls = (mockPlayOneShot as ReturnType<typeof vi.fn>).mock.calls.filter(
            (c) => c[0] === 'hover_button',
        );
        expect(hoverCalls).toHaveLength(1);
    });

    it('two separate buttons side-by-side each fire hover when stable', () => {
        render(
            <Wrapper>
                <HudButton aria-label="button-a">A</HudButton>
                <HudButton aria-label="button-b">B</HudButton>
            </Wrapper>,
        );
        const btnA = screen.getByRole('button', { name: 'button-a' });
        const btnB = screen.getByRole('button', { name: 'button-b' });

        // Enter A, wait long enough to fire
        fireEvent.mouseEnter(btnA);
        vi.advanceTimersByTime(200);

        // Enter B, wait long enough to fire
        fireEvent.mouseEnter(btnB);
        vi.advanceTimersByTime(200);

        const hoverCalls = (mockPlayOneShot as ReturnType<typeof vi.fn>).mock.calls.filter(
            (c) => c[0] === 'hover_button',
        );
        expect(hoverCalls).toHaveLength(2);
    });
});

describe('HudButton — disabled prop', () => {
    it('click on disabled button does NOT fire click SFX', () => {
        renderButton({ disabled: true });
        fireEvent.click(screen.getByRole('button'));
        const clickCalls = (mockPlayOneShot as ReturnType<typeof vi.fn>).mock.calls.filter(
            (c) => c[0] === 'click',
        );
        expect(clickCalls).toHaveLength(0);
    });

    it('click on disabled button does NOT call onClick', () => {
        const onClick = vi.fn();
        renderButton({ disabled: true, onClick });
        fireEvent.click(screen.getByRole('button'));
        expect(onClick).not.toHaveBeenCalled();
    });

    it('mouseenter on disabled button does NOT fire hover SFX', () => {
        renderButton({ disabled: true });
        fireEvent.mouseEnter(screen.getByRole('button'));
        vi.advanceTimersByTime(300);
        const hoverCalls = (mockPlayOneShot as ReturnType<typeof vi.fn>).mock.calls.filter(
            (c) => c[0] === 'hover_button',
        );
        expect(hoverCalls).toHaveLength(0);
    });

    it('disabled button has the HTML disabled attribute', () => {
        renderButton({ disabled: true });
        expect(screen.getByRole('button')).toBeDisabled();
    });
});

describe('HudButton — variant classes', () => {
    it('default variant does not add variant class modifier', () => {
        const { container } = renderButton({ variant: 'default' });
        expect(container.firstChild).not.toHaveClass('hud-btn--ghost');
        expect(container.firstChild).not.toHaveClass('hud-btn--primary');
    });

    it('ghost variant adds hud-btn--ghost class', () => {
        const { container } = renderButton({ variant: 'ghost' });
        expect(container.querySelector('.hud-btn--ghost')).toBeInTheDocument();
    });

    it('primary variant adds hud-btn--primary class', () => {
        const { container } = renderButton({ variant: 'primary' });
        expect(container.querySelector('.hud-btn--primary')).toBeInTheDocument();
    });
});
