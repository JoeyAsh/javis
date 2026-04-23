import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { PanelRails } from '../PanelRails';

describe('PanelRails', () => {
    it('renders with lib-panel-rails class', () => {
        const { container } = render(<PanelRails />);
        expect(container.querySelector('.lib-panel-rails')).toBeDefined();
    });

    it('renders left and right rail elements', () => {
        const { container } = render(<PanelRails />);
        expect(container.querySelector('.lib-panel-rails__rail--l')).toBeDefined();
        expect(container.querySelector('.lib-panel-rails__rail--r')).toBeDefined();
    });

    it('does not have visible class by default', () => {
        const { container } = render(<PanelRails />);
        expect(container.querySelector('.lib-panel-rails')?.classList.contains('visible')).toBe(
            false,
        );
    });

    it('adds visible class when visible=true', () => {
        const { container } = render(<PanelRails visible />);
        expect(container.querySelector('.lib-panel-rails')?.classList.contains('visible')).toBe(
            true,
        );
    });

    it('merges className', () => {
        const { container } = render(<PanelRails className="extra" />);
        expect(container.querySelector('.lib-panel-rails')?.classList.contains('extra')).toBe(true);
    });
});
