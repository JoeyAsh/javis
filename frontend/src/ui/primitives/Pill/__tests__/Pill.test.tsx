import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Pill } from '../Pill';

describe('Pill', () => {
    it('renders children as a span', () => {
        render(<Pill>ONLINE</Pill>);
        expect(screen.getByText('ONLINE')).toBeDefined();
    });

    it('default variant has border-border class', () => {
        const { container } = render(<Pill>X</Pill>);
        expect(container.querySelector('span')?.className).toContain('border-border');
    });

    it('ok variant has text-success class', () => {
        const { container } = render(<Pill variant="ok">OK</Pill>);
        expect(container.querySelector('span')?.className).toContain('text-success');
    });

    it('warn variant has text-warning class', () => {
        const { container } = render(<Pill variant="warn">WARN</Pill>);
        expect(container.querySelector('span')?.className).toContain('text-warning');
    });

    it('err variant has text-error class', () => {
        const { container } = render(<Pill variant="err">ERR</Pill>);
        expect(container.querySelector('span')?.className).toContain('text-error');
    });

    it('info variant has text-accent-bright class', () => {
        const { container } = render(<Pill variant="info">INFO</Pill>);
        expect(container.querySelector('span')?.className).toContain('text-accent-bright');
    });

    it('className prop merges', () => {
        const { container } = render(<Pill className="extra-class">X</Pill>);
        expect(container.querySelector('span')?.className).toContain('extra-class');
        expect(container.querySelector('span')?.className).toContain('font-mono');
    });
});
