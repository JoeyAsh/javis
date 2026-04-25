import { describe, it, expect, vi } from 'vitest';
import { render, fireEvent } from '@testing-library/react';
import React from 'react';
import { PushToTalkButton } from '../PushToTalkButton';
import { SfxContext } from '@core/audio';
import type { SfxContextValue } from '@core/audio';
import type { SfxEvent } from '@core/audio';

type MockFn = ReturnType<typeof vi.fn> & ((event: SfxEvent) => void);

function makeSfx(): { playOneShot: MockFn; play: MockFn; stop: MockFn } & SfxContextValue {
    return { playOneShot: vi.fn() as MockFn, play: vi.fn() as MockFn, stop: vi.fn() as MockFn };
}

function renderWithSfx(sfx: SfxContextValue, ui: React.ReactElement) {
    return render(<SfxContext.Provider value={sfx}>{ui}</SfxContext.Provider>);
}

describe('PushToTalkButton — visual', () => {
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

    it('has data-sfx-hover="button" attribute', () => {
        const { container } = render(<PushToTalkButton />);
        expect(container.querySelector('[data-sfx-hover="button"]')).not.toBeNull();
    });
});

describe('PushToTalkButton — SFX', () => {
    it('plays hover_button on mouseenter', () => {
        const sfx = makeSfx();
        const { getByRole } = renderWithSfx(sfx, <PushToTalkButton />);
        fireEvent.mouseEnter(getByRole('button'));
        expect(sfx.playOneShot).toHaveBeenCalledWith('hover_button');
    });

    it('plays click on click', () => {
        const sfx = makeSfx();
        const { getByRole } = renderWithSfx(sfx, <PushToTalkButton />);
        fireEvent.click(getByRole('button'));
        expect(sfx.playOneShot).toHaveBeenCalledWith('click');
    });
});
