import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { GridBackground } from '../GridBackground';

describe('GridBackground', () => {
    it('renders a div with aria-hidden', () => {
        const { container } = render(<GridBackground />);
        const el = container.querySelector('[aria-hidden]');
        expect(el).toBeDefined();
    });

    it('has fixed inset-0 positioning', () => {
        const { container } = render(<GridBackground />);
        const el = container.querySelector('div');
        expect(el?.className).toContain('fixed');
        expect(el?.className).toContain('inset-0');
    });

    it('pointer-events-none is set', () => {
        const { container } = render(<GridBackground />);
        expect(container.querySelector('div')?.className).toContain('pointer-events-none');
    });

    it('className merges', () => {
        const { container } = render(<GridBackground className="my-grid" />);
        expect(container.querySelector('div')?.className).toContain('my-grid');
    });

    it('drift prop sets animation style', () => {
        const { container } = render(<GridBackground drift />);
        const el = container.querySelector('div') as HTMLElement;
        expect(el.style.animation).toContain('jlib-grid-drift');
    });

    it('no animation without drift', () => {
        const { container } = render(<GridBackground />);
        const el = container.querySelector('div') as HTMLElement;
        expect(el.style.animation).toBeFalsy();
    });
});
