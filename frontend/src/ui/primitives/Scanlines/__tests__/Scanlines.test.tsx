import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Scanlines } from '../Scanlines';

describe('Scanlines', () => {
    it('renders children', () => {
        render(
            <Scanlines>
                <span>content</span>
            </Scanlines>,
        );
        expect(screen.getByText('content')).toBeDefined();
    });

    it('renders the scanline overlay span', () => {
        const { container } = render(
            <Scanlines>
                <div>x</div>
            </Scanlines>,
        );
        const overlay = container.querySelector('span[aria-hidden]');
        expect(overlay).toBeDefined();
    });

    it('sweep=false renders no sweep span by default', () => {
        const { container } = render(
            <Scanlines>
                <div>x</div>
            </Scanlines>,
        );
        const spans = container.querySelectorAll('span[aria-hidden]');
        // Only the scanline span, no sweep wrapper
        expect(spans.length).toBe(1);
    });

    it('sweep=true renders additional sweep span', () => {
        const { container } = render(
            <Scanlines sweep>
                <div>x</div>
            </Scanlines>,
        );
        const spans = container.querySelectorAll('span[aria-hidden]');
        expect(spans.length).toBe(2);
    });

    it('className merges on root', () => {
        const { container } = render(
            <Scanlines className="my-scanlines">
                <div>x</div>
            </Scanlines>,
        );
        expect(container.querySelector('div')?.className).toContain('my-scanlines');
    });
});
