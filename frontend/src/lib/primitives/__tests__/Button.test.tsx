import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Button } from '../Button';

describe('Button', () => {
    it('renders children as a button element', () => {
        render(<Button>CLICK ME</Button>);
        expect(screen.getByRole('button', { name: 'CLICK ME' })).toBeDefined();
    });

    it('variant=primary has bg-accent class', () => {
        const { container } = render(<Button variant="primary">P</Button>);
        const btn = container.querySelector('button');
        expect(btn?.className).toContain('bg-accent');
    });

    it('variant=ghost has border-border class', () => {
        const { container } = render(<Button variant="ghost">G</Button>);
        const btn = container.querySelector('button');
        expect(btn?.className).toContain('border-border');
    });

    it('variant=danger has text-error class', () => {
        const { container } = render(<Button variant="danger">D</Button>);
        const btn = container.querySelector('button');
        expect(btn?.className).toContain('text-error');
    });

    it('size=sm has smaller padding class', () => {
        const { container } = render(<Button size="sm">S</Button>);
        const btn = container.querySelector('button');
        expect(btn?.className).toContain('px-[10px]');
    });

    it('className prop merges with base classes', () => {
        const { container } = render(<Button className="my-custom-class">M</Button>);
        const btn = container.querySelector('button');
        expect(btn?.className).toContain('my-custom-class');
        expect(btn?.className).toContain('font-mono');
    });

    it('onClick fires when clicked', () => {
        const handler = vi.fn();
        render(<Button onClick={handler}>X</Button>);
        fireEvent.click(screen.getByRole('button'));
        expect(handler).toHaveBeenCalledTimes(1);
    });

    it('disabled button does not fire onClick', () => {
        const handler = vi.fn();
        render(
            <Button disabled onClick={handler}>
                D
            </Button>,
        );
        const btn = screen.getByRole('button');
        fireEvent.click(btn);
        expect(handler).not.toHaveBeenCalled();
    });

    it('disabled attribute is set on element', () => {
        render(<Button disabled>D</Button>);
        const btn = screen.getByRole('button');
        expect((btn as HTMLButtonElement).disabled).toBe(true);
    });
});
