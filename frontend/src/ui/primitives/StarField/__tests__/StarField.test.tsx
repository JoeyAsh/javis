import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { StarField } from '../StarField';

describe('StarField', () => {
    it('renders with lib-starfield class', () => {
        const { container } = render(<StarField />);
        expect(container.querySelector('.lib-starfield')).toBeDefined();
    });

    it('renders default 60 stars', () => {
        const { container } = render(<StarField />);
        const stars = container.querySelectorAll('.lib-starfield__star');
        expect(stars).toHaveLength(60);
    });

    it('respects custom count prop', () => {
        const { container } = render(<StarField count={10} />);
        const stars = container.querySelectorAll('.lib-starfield__star');
        expect(stars).toHaveLength(10);
    });

    it('merges className', () => {
        const { container } = render(<StarField className="extra" />);
        expect(container.querySelector('.lib-starfield')?.classList.contains('extra')).toBe(true);
    });

    it('stars have left and top inline styles', () => {
        const { container } = render(<StarField count={3} />);
        const stars = container.querySelectorAll<HTMLElement>('.lib-starfield__star');
        stars.forEach((star: HTMLElement) => {
            expect(star.style.left).toBeTruthy();
            expect(star.style.top).toBeTruthy();
        });
    });

    it('has aria-hidden for decorative use', () => {
        const { container } = render(<StarField />);
        expect(container.querySelector('.lib-starfield')?.getAttribute('aria-hidden')).toBe('true');
    });
});
