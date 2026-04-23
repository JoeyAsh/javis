import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { PanelBloom } from '../PanelBloom';

describe('PanelBloom', () => {
    it('renders with lib-panel-bloom class', () => {
        const { container } = render(<PanelBloom />);
        expect(container.querySelector('.lib-panel-bloom')).toBeDefined();
    });

    it('does not have active class by default', () => {
        const { container } = render(<PanelBloom />);
        expect(container.querySelector('.lib-panel-bloom')?.classList.contains('active')).toBe(
            false,
        );
    });

    it('adds active class when active=true', () => {
        const { container } = render(<PanelBloom active />);
        expect(container.querySelector('.lib-panel-bloom')?.classList.contains('active')).toBe(
            true,
        );
    });

    it('merges className', () => {
        const { container } = render(<PanelBloom className="extra" />);
        expect(container.querySelector('.lib-panel-bloom')?.classList.contains('extra')).toBe(true);
    });

    it('has aria-hidden for decorative use', () => {
        const { container } = render(<PanelBloom />);
        expect(container.querySelector('.lib-panel-bloom')?.getAttribute('aria-hidden')).toBe(
            'true',
        );
    });
});
