import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render } from '@testing-library/react';
import { HUDShell } from '../HUDShell';

// Mock requestAnimationFrame for any RAF-driven components inside
let rafId = 0;
beforeEach(() => {
    vi.spyOn(globalThis, 'requestAnimationFrame').mockImplementation((_cb) => {
        rafId++;
        // Don't call _cb — keep animations inert in tests
        return rafId;
    });
    vi.spyOn(globalThis, 'cancelAnimationFrame').mockImplementation(() => undefined);
});

afterEach(() => {
    vi.restoreAllMocks();
});

describe('HUDShell', () => {
    it('renders without crashing', () => {
        const { container } = render(<HUDShell />);
        expect(container.querySelector('.hud-shell')).toBeDefined();
    });

    it('renders Scene by default', () => {
        const { container } = render(<HUDShell />);
        expect(container.querySelector('.lib-scene')).toBeDefined();
    });

    it('renders Reactor by default', () => {
        const { container } = render(<HUDShell />);
        expect(container.querySelector('.lib-reactor')).toBeDefined();
    });

    it('renders ViewportCorners by default', () => {
        const { container } = render(<HUDShell />);
        expect(container.querySelector('.lib-viewport-corner')).toBeDefined();
    });

    it('omits Reactor when reactor=false', () => {
        const { container } = render(<HUDShell reactor={false} />);
        expect(container.querySelector('.lib-reactor')).toBeNull();
    });

    it('omits ViewportCorners when viewportCorners=false', () => {
        const { container } = render(<HUDShell viewportCorners={false} />);
        expect(container.querySelector('.lib-viewport-corner')).toBeNull();
    });

    it('adds idle class when idle=true', () => {
        const { container } = render(<HUDShell idle />);
        expect(container.querySelector('.hud-shell')?.classList.contains('idle')).toBe(true);
    });

    it('does not have idle class by default', () => {
        const { container } = render(<HUDShell />);
        expect(container.querySelector('.hud-shell')?.classList.contains('idle')).toBe(false);
    });

    it('adds is-working class when working=true', () => {
        const { container } = render(<HUDShell working />);
        expect(container.querySelector('.hud-shell')?.classList.contains('is-working')).toBe(true);
    });

    it('renders topbar slot', () => {
        const { getByText } = render(<HUDShell topbar={<div>TOP BAR</div>} />);
        expect(getByText('TOP BAR')).toBeDefined();
    });

    it('renders orb slot', () => {
        const { getByText } = render(<HUDShell orb={<div>ORB</div>} />);
        expect(getByText('ORB')).toBeDefined();
    });

    it('renders children slot', () => {
        const { getByText } = render(
            <HUDShell>
                <div>PANEL</div>
            </HUDShell>,
        );
        expect(getByText('PANEL')).toBeDefined();
    });

    it('renders dock slot', () => {
        const { getByText } = render(<HUDShell dock={<div>DOCK</div>} />);
        expect(getByText('DOCK')).toBeDefined();
    });

    it('merges className', () => {
        const { container } = render(<HUDShell className="extra" />);
        expect(container.querySelector('.hud-shell')?.classList.contains('extra')).toBe(true);
    });
});
