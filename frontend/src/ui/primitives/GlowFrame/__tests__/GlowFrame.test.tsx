import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { GlowFrame } from '../GlowFrame';

describe('GlowFrame', () => {
    it('renders children', () => {
        render(
            <GlowFrame>
                <span>inner</span>
            </GlowFrame>,
        );
        expect(screen.getByText('inner')).toBeDefined();
    });

    it('has border class', () => {
        const { container } = render(<GlowFrame>x</GlowFrame>);
        expect(container.querySelector('div')?.className).toContain('border');
    });

    it('static strong mode sets box-shadow style', () => {
        const { container } = render(<GlowFrame strong>x</GlowFrame>);
        const el = container.querySelector('div') as HTMLElement;
        expect(el.style.boxShadow).toContain('var(--glow-strong)');
    });

    it('breathe mode sets animation style', () => {
        const { container } = render(<GlowFrame breathe>x</GlowFrame>);
        const el = container.querySelector('div') as HTMLElement;
        expect(el.style.animation).toContain('jlib-glow-breathe');
    });

    it('className merges', () => {
        const { container } = render(<GlowFrame className="extra">x</GlowFrame>);
        expect(container.querySelector('div')?.className).toContain('extra');
    });
});
