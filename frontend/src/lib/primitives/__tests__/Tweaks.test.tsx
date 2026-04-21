import { describe, it, expect, vi } from 'vitest';
import { render, fireEvent } from '@testing-library/react';
import { Tweaks, TWEAKS_DEFAULTS } from '../Tweaks';

describe('Tweaks', () => {
    it('renders without crashing', () => {
        const { container } = render(
            <Tweaks open={false} tweaks={TWEAKS_DEFAULTS} onChange={() => undefined} />,
        );
        expect(container.querySelector('.lib-tweaks')).toBeDefined();
    });

    it('does not have open class when open=false', () => {
        const { container } = render(
            <Tweaks open={false} tweaks={TWEAKS_DEFAULTS} onChange={() => undefined} />,
        );
        expect(container.querySelector('.lib-tweaks')?.classList.contains('open')).toBe(false);
    });

    it('has open class when open=true', () => {
        const { container } = render(
            <Tweaks open tweaks={TWEAKS_DEFAULTS} onChange={() => undefined} />,
        );
        expect(container.querySelector('.lib-tweaks')?.classList.contains('open')).toBe(true);
    });

    it('renders heading', () => {
        const { getByText } = render(
            <Tweaks open tweaks={TWEAKS_DEFAULTS} onChange={() => undefined} />,
        );
        expect(getByText('◈ TWEAKS')).toBeDefined();
    });

    it('renders hue slider with current value', () => {
        const { container } = render(
            <Tweaks open tweaks={{ ...TWEAKS_DEFAULTS, hue: 180 }} onChange={() => undefined} />,
        );
        const slider = container.querySelector(
            'input[type="range"]#lib-tweaks-hue',
        ) as HTMLInputElement | null;
        expect(slider?.value).toBe('180');
    });

    it('calls onChange when hue slider changes', () => {
        const handler = vi.fn();
        const { container } = render(<Tweaks open tweaks={TWEAKS_DEFAULTS} onChange={handler} />);
        const slider = container.querySelector(
            'input[type="range"]#lib-tweaks-hue',
        ) as HTMLInputElement;
        fireEvent.change(slider, { target: { value: '100' } });
        expect(handler).toHaveBeenCalledWith({ ...TWEAKS_DEFAULTS, hue: 100 });
    });

    it('calls onChange when glow slider changes', () => {
        const handler = vi.fn();
        const { container } = render(<Tweaks open tweaks={TWEAKS_DEFAULTS} onChange={handler} />);
        const slider = container.querySelector(
            'input[type="range"]#lib-tweaks-glow',
        ) as HTMLInputElement;
        fireEvent.change(slider, { target: { value: '50' } });
        expect(handler).toHaveBeenCalledWith({ ...TWEAKS_DEFAULTS, glow: 50 });
    });

    it('calls onChange when Scanlines toggle clicked', () => {
        const handler = vi.fn();
        const { getByLabelText } = render(
            <Tweaks open tweaks={TWEAKS_DEFAULTS} onChange={handler} />,
        );
        fireEvent.click(getByLabelText('Scanlines'));
        expect(handler).toHaveBeenCalledWith({ ...TWEAKS_DEFAULTS, scan: false });
    });

    it('calls onChange when Grid toggle clicked', () => {
        const handler = vi.fn();
        const { getByLabelText } = render(
            <Tweaks open tweaks={TWEAKS_DEFAULTS} onChange={handler} />,
        );
        fireEvent.click(getByLabelText('Grid'));
        expect(handler).toHaveBeenCalledWith({ ...TWEAKS_DEFAULTS, grid: false });
    });

    it('calls onChange when swatch clicked', () => {
        const handler = vi.fn();
        const { getByLabelText } = render(
            <Tweaks open tweaks={TWEAKS_DEFAULTS} onChange={handler} />,
        );
        fireEvent.click(getByLabelText('Hue 28'));
        expect(handler).toHaveBeenCalledWith({ ...TWEAKS_DEFAULTS, hue: 28 });
    });

    it('active swatch has active class', () => {
        const { getByLabelText } = render(
            <Tweaks open tweaks={{ ...TWEAKS_DEFAULTS, hue: 215 }} onChange={() => undefined} />,
        );
        expect(getByLabelText('Hue 215').classList.contains('active')).toBe(true);
    });

    it('merges className', () => {
        const { container } = render(
            <Tweaks open tweaks={TWEAKS_DEFAULTS} onChange={() => undefined} className="extra" />,
        );
        expect(container.querySelector('.lib-tweaks')?.classList.contains('extra')).toBe(true);
    });
});
