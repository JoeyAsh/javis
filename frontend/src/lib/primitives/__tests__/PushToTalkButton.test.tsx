import { describe, it, expect, vi } from 'vitest';
import { render, fireEvent } from '@testing-library/react';
import { PushToTalkButton } from '../PushToTalkButton';

describe('PushToTalkButton', () => {
    it('renders without crashing', () => {
        const { container } = render(<PushToTalkButton />);
        expect(container.querySelector('.lib-ptt')).toBeDefined();
    });

    it('renders a button element', () => {
        const { getByRole } = render(<PushToTalkButton />);
        expect(getByRole('button')).toBeDefined();
    });

    it('has default aria-label "Push to talk"', () => {
        const { getByRole } = render(<PushToTalkButton />);
        expect(getByRole('button').getAttribute('aria-label')).toBe('Push to talk');
    });

    it('uses custom ariaLabel prop', () => {
        const { getByRole } = render(<PushToTalkButton ariaLabel="Record audio" />);
        expect(getByRole('button').getAttribute('aria-label')).toBe('Record audio');
    });

    it('does not have active class when active=false', () => {
        const { container } = render(<PushToTalkButton active={false} />);
        expect(container.querySelector('.lib-ptt')?.classList.contains('active')).toBe(false);
    });

    it('adds active class when active=true', () => {
        const { container } = render(<PushToTalkButton active />);
        expect(container.querySelector('.lib-ptt')?.classList.contains('active')).toBe(true);
    });

    it('sets aria-pressed based on active prop', () => {
        const { getByRole, rerender } = render(<PushToTalkButton active={false} />);
        expect(getByRole('button').getAttribute('aria-pressed')).toBe('false');
        rerender(<PushToTalkButton active />);
        expect(getByRole('button').getAttribute('aria-pressed')).toBe('true');
    });

    it('calls onClick when clicked', () => {
        const handler = vi.fn();
        const { getByRole } = render(<PushToTalkButton onClick={handler} />);
        fireEvent.click(getByRole('button'));
        expect(handler).toHaveBeenCalledOnce();
    });

    it('renders rim element', () => {
        const { container } = render(<PushToTalkButton />);
        expect(container.querySelector('.lib-ptt__rim')).toBeDefined();
    });

    it('renders children instead of default icon when provided', () => {
        const { getByText } = render(<PushToTalkButton>TALK</PushToTalkButton>);
        expect(getByText('TALK')).toBeDefined();
    });

    it('merges className', () => {
        const { container } = render(<PushToTalkButton className="extra" />);
        expect(container.querySelector('.lib-ptt')?.classList.contains('extra')).toBe(true);
    });
});
