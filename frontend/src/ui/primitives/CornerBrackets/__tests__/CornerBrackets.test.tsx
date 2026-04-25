import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { CornerBrackets } from '../CornerBrackets';

describe('CornerBrackets', () => {
    it('renders children', () => {
        render(
            <CornerBrackets>
                <span>inner</span>
            </CornerBrackets>,
        );
        expect(screen.getByText('inner')).toBeDefined();
    });

    it('renders 4 corner spans', () => {
        const { container } = render(
            <CornerBrackets>
                <div>x</div>
            </CornerBrackets>,
        );
        const spans = container.querySelectorAll('span[aria-hidden]');
        expect(spans.length).toBe(4);
    });

    it('default opacity on unfocused corners is 0.7', () => {
        const { container } = render(
            <CornerBrackets>
                <div>x</div>
            </CornerBrackets>,
        );
        const span = container.querySelector('span[aria-hidden]') as HTMLElement;
        expect(span.style.opacity).toBe('0.7');
    });

    it('focused opacity is 1', () => {
        const { container } = render(
            <CornerBrackets focused>
                <div>x</div>
            </CornerBrackets>,
        );
        const span = container.querySelector('span[aria-hidden]') as HTMLElement;
        expect(span.style.opacity).toBe('1');
    });

    it('className merges on wrapper', () => {
        const { container } = render(
            <CornerBrackets className="extra">
                <div>x</div>
            </CornerBrackets>,
        );
        expect(container.querySelector('div')?.className).toContain('extra');
        expect(container.querySelector('div')?.className).toContain('relative');
    });
});
