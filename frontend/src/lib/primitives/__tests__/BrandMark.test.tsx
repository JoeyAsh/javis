import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { BrandMark } from '../BrandMark';

describe('BrandMark', () => {
    it('renders the JARVIS mark text', () => {
        render(<BrandMark />);
        expect(screen.getByText('J A R V I S')).toBeDefined();
    });

    it('sub=false does not render MK XLII', () => {
        render(<BrandMark />);
        expect(screen.queryByText('MK XLII')).toBeNull();
    });

    it('sub=true renders MK XLII', () => {
        render(<BrandMark sub />);
        expect(screen.getByText('MK XLII')).toBeDefined();
    });

    it('has text-text-muted class on mark', () => {
        const { container } = render(<BrandMark />);
        const span = container.querySelector('span');
        expect(span?.className).toContain('text-text-muted');
    });

    it('className merges on wrapper', () => {
        const { container } = render(<BrandMark className="my-brand" />);
        expect(container.querySelector('div')?.className).toContain('my-brand');
    });
});
