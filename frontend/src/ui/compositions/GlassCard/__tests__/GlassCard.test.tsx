import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { GlassCard } from '../GlassCard';

describe('GlassCard', () => {
    it('renders children', () => {
        render(
            <GlassCard>
                <span>body content</span>
            </GlassCard>,
        );
        expect(screen.getByText('body content')).toBeDefined();
    });

    it('renders title when provided', () => {
        render(
            <GlassCard title="CPU">
                <span>42%</span>
            </GlassCard>,
        );
        expect(screen.getByText('CPU')).toBeDefined();
    });

    it('no title means no header dot rendered in heading', () => {
        const { container } = render(
            <GlassCard>
                <span>x</span>
            </GlassCard>,
        );
        // Header section should not exist when no title
        const header = container.querySelector('.border-b.border-border');
        expect(header).toBeNull();
    });

    it('focused prop propagates to inner Panel (adds shadow-glow)', () => {
        const { container } = render(
            <GlassCard focused title="T">
                <span>x</span>
            </GlassCard>,
        );
        const panel = container.querySelector('.shadow-glow');
        expect(panel).toBeDefined();
    });

    it('className merges on CornerBrackets wrapper', () => {
        const { container } = render(<GlassCard className="my-card">x</GlassCard>);
        // The outer-most element should have class
        expect(container.querySelector('div')?.className).toContain('my-card');
    });
});
