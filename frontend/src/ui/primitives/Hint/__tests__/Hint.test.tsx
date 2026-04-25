import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { Hint } from '../Hint';

describe('Hint', () => {
    it('renders without crashing', () => {
        const { container } = render(<Hint>PUSH TO TALK</Hint>);
        expect(container.querySelector('.lib-hint')).toBeDefined();
    });

    it('defaults to fixed-br position class', () => {
        const { container } = render(<Hint>hint</Hint>);
        expect(container.querySelector('.lib-hint')?.classList.contains('fixed-br')).toBe(true);
    });

    it('applies inline class when position=inline', () => {
        const { container } = render(<Hint position="inline">hint</Hint>);
        expect(container.querySelector('.lib-hint')?.classList.contains('inline')).toBe(true);
        expect(container.querySelector('.lib-hint')?.classList.contains('fixed-br')).toBe(false);
    });

    it('renders children text', () => {
        const { getByText } = render(<Hint>PUSH TO TALK</Hint>);
        expect(getByText('PUSH TO TALK')).toBeDefined();
    });

    it('merges className', () => {
        const { container } = render(<Hint className="extra">hint</Hint>);
        expect(container.querySelector('.lib-hint')?.classList.contains('extra')).toBe(true);
    });

    describe('Hint.Key', () => {
        it('renders as kbd element', () => {
            const { container } = render(
                <Hint>
                    <Hint.Key>SPACE</Hint.Key>
                </Hint>,
            );
            expect(container.querySelector('kbd.lib-hint__kbd')).toBeDefined();
        });

        it('renders key text', () => {
            const { getByText } = render(
                <Hint>
                    <Hint.Key>CTRL+.</Hint.Key>
                </Hint>,
            );
            expect(getByText('CTRL+.')).toBeDefined();
        });

        it('merges className on Key', () => {
            const { container } = render(
                <Hint>
                    <Hint.Key className="key-extra">SPACE</Hint.Key>
                </Hint>,
            );
            expect(container.querySelector('kbd')?.classList.contains('key-extra')).toBe(true);
        });
    });
});
