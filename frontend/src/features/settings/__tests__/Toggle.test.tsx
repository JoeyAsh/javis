/**
 * Toggle — Vitest + RTL unit tests.
 */
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { Toggle } from '../components/Toggle';

describe('Toggle', () => {
    it('renders label text', () => {
        render(<Toggle checked={false} onChange={vi.fn()} label="Test Toggle" />);
        expect(screen.getByText('Test Toggle')).toBeTruthy();
    });

    it('renders description when provided', () => {
        render(
            <Toggle
                checked={false}
                onChange={vi.fn()}
                label="Label"
                description="Some description"
            />,
        );
        expect(screen.getByText('Some description')).toBeTruthy();
    });

    it('does not render description when omitted', () => {
        render(<Toggle checked={false} onChange={vi.fn()} label="Label" />);
        expect(screen.queryByText('Some description')).toBeNull();
    });

    it('fires onChange(true) when unchecked and clicked', () => {
        const onChange = vi.fn();
        render(<Toggle checked={false} onChange={onChange} label="Toggle" />);
        const btn = screen.getByRole('switch');
        fireEvent.click(btn);
        expect(onChange).toHaveBeenCalledWith(true);
    });

    it('fires onChange(false) when checked and clicked', () => {
        const onChange = vi.fn();
        render(<Toggle checked={true} onChange={onChange} label="Toggle" />);
        const btn = screen.getByRole('switch');
        fireEvent.click(btn);
        expect(onChange).toHaveBeenCalledWith(false);
    });

    it('sets aria-checked to reflect checked state', () => {
        const { rerender } = render(<Toggle checked={false} onChange={vi.fn()} label="Toggle" />);
        expect(screen.getByRole('switch').getAttribute('aria-checked')).toBe('false');
        rerender(<Toggle checked={true} onChange={vi.fn()} label="Toggle" />);
        expect(screen.getByRole('switch').getAttribute('aria-checked')).toBe('true');
    });
});
