import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { WaveStrip } from '../WaveStrip';

describe('WaveStrip', () => {
    it('renders without crashing', () => {
        const { container } = render(<WaveStrip />);
        expect(container.querySelector('.lib-wave-strip')).toBeDefined();
    });

    it('renders 7 bars', () => {
        const { container } = render(<WaveStrip />);
        expect(container.querySelectorAll('.lib-wave-strip__bar')).toHaveLength(7);
    });

    it('adds inactive class when active=false', () => {
        const { container } = render(<WaveStrip active={false} />);
        expect(container.querySelector('.lib-wave-strip')?.classList.contains('inactive')).toBe(
            true,
        );
    });

    it('does not add inactive class when active=true', () => {
        const { container } = render(<WaveStrip active />);
        expect(container.querySelector('.lib-wave-strip')?.classList.contains('inactive')).toBe(
            false,
        );
    });

    it('adds mirrored class when mirrored=true', () => {
        const { container } = render(<WaveStrip mirrored />);
        expect(container.querySelector('.lib-wave-strip')?.classList.contains('mirrored')).toBe(
            true,
        );
    });

    it('is aria-hidden', () => {
        const { container } = render(<WaveStrip />);
        expect(container.querySelector('.lib-wave-strip')?.getAttribute('aria-hidden')).toBe(
            'true',
        );
    });

    it('merges className', () => {
        const { container } = render(<WaveStrip className="extra" />);
        expect(container.querySelector('.lib-wave-strip')?.classList.contains('extra')).toBe(true);
    });
});
