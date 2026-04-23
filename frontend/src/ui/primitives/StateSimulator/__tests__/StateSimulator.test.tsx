import { describe, it, expect, vi } from 'vitest';
import { render, fireEvent } from '@testing-library/react';
import React from 'react';
import { StateSimulator } from '../StateSimulator';
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

describe('StateSimulator — visual', () => {
    it('renders without crashing', () => {
        const { container } = render(<StateSimulator state="idle" onChange={() => undefined} />);
        expect(container.querySelector('.lib-sim')).toBeDefined();
    });

    it('renders default label', () => {
        const { getByText } = render(<StateSimulator state="idle" onChange={() => undefined} />);
        expect(getByText('◈ ORB STATE')).toBeDefined();
    });

    it('renders custom label', () => {
        const { getByText } = render(
            <StateSimulator state="idle" onChange={() => undefined} label="◈ CUSTOM" />,
        );
        expect(getByText('◈ CUSTOM')).toBeDefined();
    });

    it('renders 5 state buttons', () => {
        const { container } = render(<StateSimulator state="idle" onChange={() => undefined} />);
        expect(container.querySelectorAll('.lib-sim__btn')).toHaveLength(5);
    });

    it('marks active button with active class', () => {
        const { container } = render(
            <StateSimulator state="listening" onChange={() => undefined} />,
        );
        const buttons = container.querySelectorAll('.lib-sim__btn');
        const listeningBtn = Array.from(buttons).find((b) => b.textContent?.includes('LISTENING'));
        expect(listeningBtn?.classList.contains('active')).toBe(true);
    });

    it('adds working class to working button when active', () => {
        const { container } = render(<StateSimulator state="working" onChange={() => undefined} />);
        const workingBtn = Array.from(container.querySelectorAll('.lib-sim__btn')).find((b) =>
            b.textContent?.includes('WORKING'),
        );
        expect(workingBtn?.classList.contains('active')).toBe(true);
        expect(workingBtn?.classList.contains('working')).toBe(true);
    });

    it('calls onChange with new state when button clicked', () => {
        const handler = vi.fn();
        const { getByText } = render(<StateSimulator state="idle" onChange={handler} />);
        fireEvent.click(getByText('THINKING'));
        expect(handler).toHaveBeenCalledWith('thinking');
    });

    it('applies fixed-top class by default', () => {
        const { container } = render(<StateSimulator state="idle" onChange={() => undefined} />);
        expect(container.querySelector('.lib-sim')?.classList.contains('fixed-top')).toBe(true);
    });

    it('applies inline class when position=inline', () => {
        const { container } = render(
            <StateSimulator state="idle" onChange={() => undefined} position="inline" />,
        );
        expect(container.querySelector('.lib-sim')?.classList.contains('inline')).toBe(true);
    });

    it('merges className', () => {
        const { container } = render(
            <StateSimulator state="idle" onChange={() => undefined} className="extra" />,
        );
        expect(container.querySelector('.lib-sim')?.classList.contains('extra')).toBe(true);
    });
});

describe('StateSimulator — SFX', () => {
    it('plays click when state button is clicked', () => {
        const sfx = makeSfx();
        const { getByText } = renderWithSfx(
            sfx,
            <StateSimulator state="idle" onChange={() => undefined} />,
        );
        fireEvent.click(getByText('THINKING'));
        expect(sfx.playOneShot).toHaveBeenCalledWith('click');
    });

    it('plays hover_button on mouseenter of state button', () => {
        const sfx = makeSfx();
        const { getByText } = renderWithSfx(
            sfx,
            <StateSimulator state="idle" onChange={() => undefined} />,
        );
        fireEvent.mouseEnter(getByText('THINKING').closest('button') as HTMLElement);
        expect(sfx.playOneShot).toHaveBeenCalledWith('hover_button');
    });
});
