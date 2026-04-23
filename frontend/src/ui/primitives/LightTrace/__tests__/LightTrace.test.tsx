import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { LightTrace } from '../LightTrace';

describe('LightTrace', () => {
    it('renders with lib-lighttrace class', () => {
        const { container } = render(<LightTrace />);
        expect(container.querySelector('.lib-lighttrace')).toBeDefined();
    });

    it('renders left and right strip elements', () => {
        const { container } = render(<LightTrace />);
        expect(container.querySelector('.lib-lighttrace__l')).toBeDefined();
        expect(container.querySelector('.lib-lighttrace__r')).toBeDefined();
    });

    it('merges className', () => {
        const { container } = render(<LightTrace className="extra" />);
        const root = container.querySelector('.lib-lighttrace');
        expect(root?.classList.contains('extra')).toBe(true);
    });

    it('applies custom color via CSS custom property', () => {
        const { container } = render(<LightTrace color="#ff0000" />);
        const root = container.querySelector<HTMLElement>('.lib-lighttrace');
        expect(root?.style.getPropertyValue('--lt-color')).toBe('#ff0000');
    });

    it('has aria-hidden for decorative use', () => {
        const { container } = render(<LightTrace />);
        expect(container.querySelector('.lib-lighttrace')?.getAttribute('aria-hidden')).toBe(
            'true',
        );
    });
});
