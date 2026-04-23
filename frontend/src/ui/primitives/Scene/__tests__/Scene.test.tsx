import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { Scene } from '../Scene';

describe('Scene', () => {
    it('renders with lib-scene class', () => {
        const { container } = render(<Scene />);
        expect(container.querySelector('.lib-scene')).toBeDefined();
    });

    it('renders grid by default', () => {
        const { container } = render(<Scene />);
        expect(container.querySelector('.lib-scene__grid')).toBeDefined();
    });

    it('does not render grid when grid=false', () => {
        const { container } = render(<Scene grid={false} />);
        expect(container.querySelector('.lib-scene__grid')).toBeNull();
    });

    it('renders scanlines by default', () => {
        const { container } = render(<Scene />);
        expect(container.querySelector('.lib-scene__scanlines')).toBeDefined();
    });

    it('does not render scanlines when scanlines=false', () => {
        const { container } = render(<Scene scanlines={false} />);
        expect(container.querySelector('.lib-scene__scanlines')).toBeNull();
    });

    it('renders stars by default (StarField inside)', () => {
        const { container } = render(<Scene />);
        expect(container.querySelector('.lib-starfield')).toBeDefined();
    });

    it('does not render stars when stars=false', () => {
        const { container } = render(<Scene stars={false} />);
        expect(container.querySelector('.lib-starfield')).toBeNull();
    });

    it('always renders vignette and noise and horizon', () => {
        const { container } = render(<Scene />);
        expect(container.querySelector('.lib-scene__vignette')).toBeDefined();
        expect(container.querySelector('.lib-scene__noise')).toBeDefined();
        expect(container.querySelector('.lib-scene__horizon')).toBeDefined();
    });

    it('merges className', () => {
        const { container } = render(<Scene className="extra" />);
        expect(container.querySelector('.lib-scene')?.classList.contains('extra')).toBe(true);
    });
});
