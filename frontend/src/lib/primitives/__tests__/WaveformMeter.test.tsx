import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { WaveformMeter } from '../WaveformMeter';

describe('WaveformMeter', () => {
    it('renders without crashing', () => {
        const { container } = render(<WaveformMeter />);
        expect(container.querySelector('.lib-meter')).toBeDefined();
    });

    it('renders 12 bars by default', () => {
        const { container } = render(<WaveformMeter />);
        expect(container.querySelectorAll('.lib-meter__bar')).toHaveLength(12);
    });

    it('renders custom barCount', () => {
        const { container } = render(<WaveformMeter barCount={6} />);
        expect(container.querySelectorAll('.lib-meter__bar')).toHaveLength(6);
    });

    it('does not add inactive class when active=true', () => {
        const { container } = render(<WaveformMeter active />);
        expect(container.querySelector('.lib-meter')?.classList.contains('inactive')).toBe(false);
    });

    it('adds inactive class when active=false', () => {
        const { container } = render(<WaveformMeter active={false} />);
        expect(container.querySelector('.lib-meter')?.classList.contains('inactive')).toBe(true);
    });

    it('adds mirrored class when mirrored=true', () => {
        const { container } = render(<WaveformMeter mirrored />);
        expect(container.querySelector('.lib-meter')?.classList.contains('mirrored')).toBe(true);
    });

    it('does not add mirrored class by default', () => {
        const { container } = render(<WaveformMeter />);
        expect(container.querySelector('.lib-meter')?.classList.contains('mirrored')).toBe(false);
    });

    it('is aria-hidden', () => {
        const { container } = render(<WaveformMeter />);
        expect(container.querySelector('.lib-meter')?.getAttribute('aria-hidden')).toBe('true');
    });

    it('merges className', () => {
        const { container } = render(<WaveformMeter className="extra" />);
        expect(container.querySelector('.lib-meter')?.classList.contains('extra')).toBe(true);
    });
});
