import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { Sparkline } from '../Sparkline';

const DATA = [5, 8, 3, 9, 6, 10, 4];

describe('Sparkline', () => {
    it('renders an svg element', () => {
        const { container } = render(<Sparkline data={DATA} />);
        expect(container.querySelector('svg')).toBeDefined();
    });

    it('renders path elements when data has 2+ points', () => {
        const { container } = render(<Sparkline data={DATA} />);
        const paths = container.querySelectorAll('path');
        expect(paths.length).toBeGreaterThan(0);
    });

    it('accent variant uses accent stroke color', () => {
        const { container } = render(<Sparkline data={DATA} variant="accent" />);
        const line = container.querySelector('path[stroke]');
        expect(line?.getAttribute('stroke')).toBe('#6ec4ff');
    });

    it('warn variant uses warn stroke color', () => {
        const { container } = render(<Sparkline data={DATA} variant="warn" />);
        const line = container.querySelector('path[stroke]');
        expect(line?.getAttribute('stroke')).toBe('#e8b24c');
    });

    it('aria-label is set when provided', () => {
        const { container } = render(<Sparkline data={DATA} aria-label="CPU chart" />);
        expect(container.querySelector('svg')?.getAttribute('aria-label')).toBe('CPU chart');
    });

    it('renders nothing when data has fewer than 2 points', () => {
        const { container } = render(<Sparkline data={[5]} />);
        const paths = container.querySelectorAll('path');
        expect(paths.length).toBe(0);
    });

    it('className merges onto svg', () => {
        const { container } = render(<Sparkline data={DATA} className="my-sparkline" />);
        expect(container.querySelector('svg')?.className.baseVal).toContain('my-sparkline');
    });
});
