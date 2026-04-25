import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Label } from '../Label';

describe('Label', () => {
    it('renders children as a span by default', () => {
        render(<Label>CPU USAGE</Label>);
        expect(screen.getByText('CPU USAGE')).toBeDefined();
    });

    it('default has text-text-secondary class', () => {
        const { container } = render(<Label>X</Label>);
        expect(container.querySelector('span')?.className).toContain('text-text-secondary');
    });

    it('dim prop gives text-text-muted class', () => {
        const { container } = render(<Label dim>X</Label>);
        expect(container.querySelector('span')?.className).toContain('text-text-muted');
    });

    it('uppercase and tracking classes present', () => {
        const { container } = render(<Label>X</Label>);
        const cls = container.querySelector('span')?.className ?? '';
        expect(cls).toContain('uppercase');
        expect(cls).toContain('tracking-[1px]');
    });

    it('htmlFor renders a label element', () => {
        const { container } = render(<Label htmlFor="my-input">NAME</Label>);
        const el = container.querySelector('label');
        expect(el).toBeDefined();
        expect(el?.htmlFor).toBe('my-input');
    });

    it('className merges', () => {
        const { container } = render(<Label className="my-extra">X</Label>);
        expect(container.querySelector('span')?.className).toContain('my-extra');
    });
});
