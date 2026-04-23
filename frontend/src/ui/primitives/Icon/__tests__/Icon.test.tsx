import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { Icon } from '../Icon';
import { Mic } from 'lucide-react';

describe('Icon', () => {
    it('renders an svg element', () => {
        const { container } = render(<Icon icon={Mic} />);
        expect(container.querySelector('svg')).toBeDefined();
    });

    it('default size md renders 14px dimensions', () => {
        const { container } = render(<Icon icon={Mic} />);
        const svg = container.querySelector('svg');
        expect(svg?.getAttribute('width')).toBe('14');
        expect(svg?.getAttribute('height')).toBe('14');
    });

    it('size sm renders 12px', () => {
        const { container } = render(<Icon icon={Mic} size="sm" />);
        const svg = container.querySelector('svg');
        expect(svg?.getAttribute('width')).toBe('12');
    });

    it('size lg renders 16px', () => {
        const { container } = render(<Icon icon={Mic} size="lg" />);
        const svg = container.querySelector('svg');
        expect(svg?.getAttribute('width')).toBe('16');
    });

    it('aria-label is passed through', () => {
        const { container } = render(<Icon icon={Mic} aria-label="microphone" />);
        expect(container.querySelector('svg')?.getAttribute('aria-label')).toBe('microphone');
    });

    it('className merges', () => {
        const { container } = render(<Icon icon={Mic} className="text-accent" />);
        expect(container.querySelector('svg')?.className.baseVal).toContain('text-accent');
    });
});
