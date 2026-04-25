import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { StatusLabel } from '../StatusLabel';

describe('StatusLabel', () => {
    it('renders without crashing', () => {
        const { container } = render(<StatusLabel state="idle" />);
        expect(container.querySelector('.lib-status-label')).toBeDefined();
    });

    it('shows READY for idle state', () => {
        const { getByText } = render(<StatusLabel state="idle" />);
        expect(getByText('READY')).toBeDefined();
    });

    it('shows listening... for listening state', () => {
        const { getByText } = render(<StatusLabel state="listening" />);
        expect(getByText('listening...')).toBeDefined();
    });

    it('shows thinking... for thinking state', () => {
        const { getByText } = render(<StatusLabel state="thinking" />);
        expect(getByText('thinking...')).toBeDefined();
    });

    it('shows speaking... for speaking state', () => {
        const { getByText } = render(<StatusLabel state="speaking" />);
        expect(getByText('speaking...')).toBeDefined();
    });

    it('shows working... for working state', () => {
        const { getByText } = render(<StatusLabel state="working" />);
        expect(getByText('working...')).toBeDefined();
    });

    it('state text does not have active class when idle', () => {
        const { container } = render(<StatusLabel state="idle" />);
        expect(
            container.querySelector('.lib-status-label__state')?.classList.contains('active'),
        ).toBe(false);
    });

    it('state text has active class when not idle', () => {
        const { container } = render(<StatusLabel state="listening" />);
        expect(
            container.querySelector('.lib-status-label__state')?.classList.contains('active'),
        ).toBe(true);
    });

    it('renders default brand mark', () => {
        const { getByText } = render(<StatusLabel state="idle" />);
        expect(getByText('J A R V I S')).toBeDefined();
    });

    it('renders custom brand prop', () => {
        const { getByText } = render(<StatusLabel state="idle" brand="UNIT 01" />);
        expect(getByText('UNIT 01')).toBeDefined();
    });

    it('merges className', () => {
        const { container } = render(<StatusLabel state="idle" className="extra" />);
        expect(container.querySelector('.lib-status-label')?.classList.contains('extra')).toBe(
            true,
        );
    });
});
