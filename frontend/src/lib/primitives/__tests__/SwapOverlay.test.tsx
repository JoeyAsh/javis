import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { SwapOverlay } from '../SwapOverlay';
import type { SlotRect } from '../../layout/SlotGrid';

const GHOST_RECT: SlotRect = { x: 100, y: 200, w: 316, h: 250 };

describe('SwapOverlay', () => {
    it('renders root element', () => {
        const { container } = render(<SwapOverlay active={false} ghostRect={null} />);
        expect(container.querySelector('.lib-swap')).toBeDefined();
    });

    it('hidden (no ghost div) when active=false', () => {
        const { container } = render(<SwapOverlay active={false} ghostRect={GHOST_RECT} />);
        expect(container.querySelector('.lib-swap__ghost')).toBeNull();
    });

    it('hidden (no ghost div) when active=true but ghostRect=null', () => {
        const { container } = render(<SwapOverlay active={true} ghostRect={null} />);
        expect(container.querySelector('.lib-swap__ghost')).toBeNull();
    });

    it('renders ghost div when active=true and ghostRect provided', () => {
        const { container } = render(<SwapOverlay active={true} ghostRect={GHOST_RECT} />);
        expect(container.querySelector('.lib-swap__ghost')).not.toBeNull();
    });

    it('ghost div is aria-hidden', () => {
        const { container } = render(<SwapOverlay active={true} ghostRect={GHOST_RECT} />);
        const root = container.querySelector('.lib-swap');
        expect(root?.getAttribute('aria-hidden')).toBe('true');
    });

    it('hovered=false does not apply hovered class to ghost', () => {
        const { container } = render(
            <SwapOverlay active={true} ghostRect={GHOST_RECT} hovered={false} />,
        );
        expect(
            container
                .querySelector('.lib-swap__ghost')
                ?.classList.contains('lib-swap__ghost--hovered'),
        ).toBe(false);
    });

    it('hovered=true applies hovered class to ghost', () => {
        const { container } = render(
            <SwapOverlay active={true} ghostRect={GHOST_RECT} hovered={true} />,
        );
        expect(
            container
                .querySelector('.lib-swap__ghost')
                ?.classList.contains('lib-swap__ghost--hovered'),
        ).toBe(true);
    });

    it('className merges without replacing base class', () => {
        const { container } = render(
            <SwapOverlay active={false} ghostRect={null} className="extra" />,
        );
        const root = container.querySelector('.lib-swap');
        expect(root?.classList.contains('extra')).toBe(true);
        expect(root?.classList.contains('lib-swap')).toBe(true);
    });

    it('ghost div is positioned at ghostRect coords', () => {
        const { container } = render(<SwapOverlay active={true} ghostRect={GHOST_RECT} />);
        const ghost = container.querySelector<HTMLDivElement>('.lib-swap__ghost');
        expect(ghost?.style.left).toBe('100px');
        expect(ghost?.style.top).toBe('200px');
        expect(ghost?.style.width).toBe('316px');
        expect(ghost?.style.height).toBe('250px');
    });
});
