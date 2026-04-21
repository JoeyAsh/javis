import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { ViewportCorners } from '../ViewportCorners';

describe('ViewportCorners', () => {
    it('renders 4 corner spans', () => {
        const { container } = render(
            <div>
                <ViewportCorners />
            </div>,
        );
        const corners = container.querySelectorAll('.lib-viewport-corner');
        expect(corners).toHaveLength(4);
    });

    it('renders tl, tr, bl, br positions', () => {
        const { container } = render(
            <div>
                <ViewportCorners />
            </div>,
        );
        expect(container.querySelector('.lib-viewport-corner.tl')).toBeDefined();
        expect(container.querySelector('.lib-viewport-corner.tr')).toBeDefined();
        expect(container.querySelector('.lib-viewport-corner.bl')).toBeDefined();
        expect(container.querySelector('.lib-viewport-corner.br')).toBeDefined();
    });

    it('merges className on each corner', () => {
        const { container } = render(
            <div>
                <ViewportCorners className="extra" />
            </div>,
        );
        const corners = container.querySelectorAll('.lib-viewport-corner');
        corners.forEach((corner: Element) => {
            expect(corner.classList.contains('extra')).toBe(true);
        });
    });
});
