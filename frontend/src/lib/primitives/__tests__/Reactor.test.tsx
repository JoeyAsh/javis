import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { Reactor } from '../Reactor';

describe('Reactor', () => {
    it('renders with lib-reactor class', () => {
        const { container } = render(<Reactor />);
        expect(container.querySelector('.lib-reactor')).toBeDefined();
    });

    it('merges className', () => {
        const { container } = render(<Reactor className="extra" />);
        expect(container.querySelector('.lib-reactor')?.classList.contains('extra')).toBe(true);
    });

    it('has aria-hidden for decorative use', () => {
        const { container } = render(<Reactor />);
        expect(container.querySelector('.lib-reactor')?.getAttribute('aria-hidden')).toBe('true');
    });
});
