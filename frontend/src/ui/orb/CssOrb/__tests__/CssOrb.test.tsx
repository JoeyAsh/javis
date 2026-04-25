import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, act } from '@testing-library/react';
import { CssOrb as Orb } from '../CssOrb';

// Mock RAF / CAF with vi.fn() spies
let rafMock: ReturnType<typeof vi.fn>;
let cafMock: ReturnType<typeof vi.fn>;
let rafId = 0;

beforeEach(() => {
    rafId = 0;
    rafMock = vi.fn((_cb: (t: number) => void) => {
        rafId += 1;
        return rafId;
    });
    cafMock = vi.fn();
    vi.stubGlobal('requestAnimationFrame', rafMock);
    vi.stubGlobal('cancelAnimationFrame', cafMock);
});

afterEach(() => {
    vi.unstubAllGlobals();
});

describe('Orb', () => {
    it('renders without crashing in idle state', () => {
        const { container } = render(<Orb state="idle" />);
        expect(container.querySelector('.orb-wrap')).toBeTruthy();
    });

    it('renders without crashing in listening state', () => {
        const { container } = render(<Orb state="listening" />);
        expect(container.querySelector('.orb-wrap')).toBeTruthy();
    });

    it('renders without crashing in thinking state', () => {
        const { container } = render(<Orb state="thinking" />);
        expect(container.querySelector('.orb-wrap')).toBeTruthy();
    });

    it('renders without crashing in speaking state', () => {
        const { container } = render(<Orb state="speaking" />);
        expect(container.querySelector('.orb-wrap')).toBeTruthy();
    });

    it('renders without crashing in working state', () => {
        const { container } = render(<Orb state="working" />);
        expect(container.querySelector('.orb-wrap')).toBeTruthy();
    });

    it('applies state class to the orb core', () => {
        const { container } = render(<Orb state="thinking" />);
        expect(container.querySelector('.orb.state-thinking')).toBeTruthy();
    });

    it('applies is-working class to orb-wrap when state is working', () => {
        const { container } = render(<Orb state="working" />);
        expect(container.querySelector('.orb-wrap.is-working')).toBeTruthy();
    });

    it('does NOT apply is-working when state is not working', () => {
        const { container } = render(<Orb state="idle" />);
        expect(container.querySelector('.orb-wrap.is-working')).toBeNull();
    });

    it('renders particles by default', () => {
        const { container } = render(<Orb state="idle" />);
        expect(container.querySelectorAll('.particle').length).toBe(6);
    });

    it('hides particles when particles={false}', () => {
        const { container } = render(<Orb state="idle" particles={false} />);
        expect(container.querySelectorAll('.particle').length).toBe(0);
    });

    it('starts RAF when particles are enabled', () => {
        render(<Orb state="idle" particles />);
        expect(rafMock).toHaveBeenCalled();
    });

    it('cancels RAF on unmount', () => {
        const { unmount } = render(<Orb state="idle" particles />);
        act(() => {
            unmount();
        });
        expect(cafMock).toHaveBeenCalled();
    });

    it('does not start RAF when particles are disabled', () => {
        rafMock.mockClear();
        render(<Orb state="idle" particles={false} />);
        expect(rafMock).not.toHaveBeenCalled();
    });

    it('merges className onto wrapper', () => {
        const { container } = render(<Orb state="idle" className="my-orb" />);
        expect(container.querySelector('.orb-wrap')?.className).toContain('my-orb');
    });

    it('renders 3 pulse rings', () => {
        const { container } = render(<Orb state="idle" />);
        const pulses = container.querySelectorAll('.pulse');
        expect(pulses.length).toBe(3);
    });

    it('renders rings by default', () => {
        const { container } = render(<Orb state="idle" />);
        expect(container.querySelectorAll('.orb-ring').length).toBeGreaterThanOrEqual(5);
        expect(container.querySelector('.orb-ring-ticks')).toBeTruthy();
    });

    it('hides rings when rings={false}', () => {
        const { container } = render(<Orb state="idle" rings={false} />);
        expect(container.querySelectorAll('.orb-ring').length).toBe(0);
        expect(container.querySelector('.orb-ring-ticks')).toBeNull();
    });

    it('renders 36 tick marks inside ring-ticks', () => {
        const { container } = render(<Orb state="idle" />);
        const ticks = container.querySelectorAll('.orb-ring-ticks i');
        expect(ticks).toHaveLength(36);
    });
});
