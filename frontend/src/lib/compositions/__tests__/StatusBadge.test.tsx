import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { StatusBadge } from '../StatusBadge';

describe('StatusBadge', () => {
    it('renders default label text', () => {
        render(<StatusBadge />);
        expect(screen.getByText('LINK · SECURE')).toBeDefined();
    });

    it('renders custom label', () => {
        render(<StatusBadge label="HIGH TEMP" />);
        expect(screen.getByText('HIGH TEMP')).toBeDefined();
    });

    it('online state dot has bg-success class', () => {
        const { container } = render(<StatusBadge state="online" />);
        const dot = container.querySelector('span.rounded-full');
        expect(dot?.className).toContain('bg-success');
    });

    it('warn state dot has bg-warning class', () => {
        const { container } = render(<StatusBadge state="warn" />);
        const dot = container.querySelector('span.rounded-full');
        expect(dot?.className).toContain('bg-warning');
    });

    it('offline state dot has bg-text-muted class', () => {
        const { container } = render(<StatusBadge state="offline" />);
        const dot = container.querySelector('span.rounded-full');
        expect(dot?.className).toContain('bg-text-muted');
    });

    it('pulse=true sets animation style on dot', () => {
        const { container } = render(<StatusBadge state="online" pulse />);
        const dot = container.querySelector('span.rounded-full') as HTMLElement;
        expect(dot.style.animation).toContain('jlib-status-pulse');
    });

    it('pulse=false no animation', () => {
        const { container } = render(<StatusBadge state="online" pulse={false} />);
        const dot = container.querySelector('span.rounded-full') as HTMLElement;
        expect(dot.style.animation).toBeFalsy();
    });

    it('className merges', () => {
        const { container } = render(<StatusBadge className="my-badge" />);
        const outer = container.querySelector('span');
        expect(outer?.className).toContain('my-badge');
    });
});
