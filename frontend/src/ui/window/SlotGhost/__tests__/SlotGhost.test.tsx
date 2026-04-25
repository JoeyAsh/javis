import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { SlotGhost } from '../SlotGhost';
import type { SlotRect } from '../../slotGrid';

const RECT: SlotRect = { x: 12, y: 72, w: 316, h: 250 };

describe('SlotGhost', () => {
    it('renders without crashing', () => {
        const { container } = render(<SlotGhost rect={RECT} />);
        expect(container.querySelector('.lib-slot-ghost')).toBeDefined();
    });

    it('is aria-hidden', () => {
        const { container } = render(<SlotGhost rect={RECT} />);
        expect(container.querySelector('.lib-slot-ghost')?.getAttribute('aria-hidden')).toBe(
            'true',
        );
    });

    it('renders at the given rect coordinates', () => {
        const { container } = render(<SlotGhost rect={RECT} />);
        const el = container.querySelector<HTMLDivElement>('.lib-slot-ghost');
        expect(el?.style.left).toBe('12px');
        expect(el?.style.top).toBe('72px');
        expect(el?.style.width).toBe('316px');
        expect(el?.style.height).toBe('250px');
    });

    it('renders label when provided', () => {
        render(<SlotGhost rect={RECT} label="L1" />);
        expect(screen.getByText('L1')).toBeDefined();
    });

    it('renders label inside .lib-slot-ghost__label span', () => {
        const { container } = render(<SlotGhost rect={RECT} label="R2" />);
        expect(container.querySelector('.lib-slot-ghost__label')).not.toBeNull();
        expect(container.querySelector('.lib-slot-ghost__label')?.textContent).toBe('R2');
    });

    it('does not render label span when label is omitted', () => {
        const { container } = render(<SlotGhost rect={RECT} />);
        expect(container.querySelector('.lib-slot-ghost__label')).toBeNull();
    });

    it('className merges without replacing base class', () => {
        const { container } = render(<SlotGhost rect={RECT} className="custom" />);
        const root = container.querySelector('.lib-slot-ghost');
        expect(root?.classList.contains('custom')).toBe(true);
        expect(root?.classList.contains('lib-slot-ghost')).toBe(true);
    });
});
