import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { Reticle } from '../Reticle';

describe('Reticle', () => {
    it('renders a presentation span', () => {
        const { container } = render(<Reticle />);
        expect(container.querySelector('[role="presentation"]')).toBeDefined();
    });

    it('has aria-hidden by default', () => {
        const { container } = render(<Reticle />);
        const el = container.querySelector('[role="presentation"]');
        expect(el?.getAttribute('aria-hidden')).toBeTruthy();
    });

    it('renders two inner spans for the crosshair lines', () => {
        const { container } = render(<Reticle />);
        const inner = container.querySelectorAll('span > span');
        expect(inner.length).toBe(2);
    });

    it('applies given size via style', () => {
        const { container } = render(<Reticle size={20} />);
        const el = container.querySelector('[role="presentation"]') as HTMLElement;
        expect(el.style.width).toBe('20px');
        expect(el.style.height).toBe('20px');
    });

    it('className merges', () => {
        const { container } = render(<Reticle className="my-reticle" />);
        expect(container.querySelector('[role="presentation"]')?.className).toContain('my-reticle');
    });
});
