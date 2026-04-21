import { describe, it, expect, vi } from 'vitest';
import { render, fireEvent } from '@testing-library/react';
import { StatusDock } from '../StatusDock';

describe('StatusDock', () => {
    it('renders without crashing', () => {
        const { container } = render(<StatusDock state="idle" />);
        expect(container.querySelector('.lib-dock')).toBeDefined();
    });

    it('renders two WaveformMeter instances', () => {
        const { container } = render(<StatusDock state="idle" />);
        expect(container.querySelectorAll('.lib-meter')).toHaveLength(2);
    });

    it('renders the PushToTalkButton', () => {
        const { container } = render(<StatusDock state="idle" />);
        expect(container.querySelector('.lib-ptt')).toBeDefined();
    });

    it('renders the StatusLabel', () => {
        const { container } = render(<StatusDock state="idle" />);
        expect(container.querySelector('.lib-status-label')).toBeDefined();
    });

    it('renders READY text for idle state', () => {
        const { getByText } = render(<StatusDock state="idle" />);
        expect(getByText('READY')).toBeDefined();
    });

    it('renders listening... text for listening state', () => {
        const { getByText } = render(<StatusDock state="listening" />);
        expect(getByText('listening...')).toBeDefined();
    });

    it('PTT button is not active when idle', () => {
        const { container } = render(<StatusDock state="idle" />);
        expect(container.querySelector('.lib-ptt')?.classList.contains('active')).toBe(false);
    });

    it('PTT button is active when not idle', () => {
        const { container } = render(<StatusDock state="listening" />);
        expect(container.querySelector('.lib-ptt')?.classList.contains('active')).toBe(true);
    });

    it('meters are inactive when idle', () => {
        const { container } = render(<StatusDock state="idle" />);
        const meters = container.querySelectorAll('.lib-meter');
        meters.forEach((m) => expect(m.classList.contains('inactive')).toBe(true));
    });

    it('meters are active when not idle', () => {
        const { container } = render(<StatusDock state="speaking" />);
        const meters = container.querySelectorAll('.lib-meter');
        meters.forEach((m) => expect(m.classList.contains('inactive')).toBe(false));
    });

    it('second meter is mirrored', () => {
        const { container } = render(<StatusDock state="idle" />);
        const meters = container.querySelectorAll('.lib-meter');
        expect(meters[1]?.classList.contains('mirrored')).toBe(true);
    });

    it('calls onPTT when PTT button clicked', () => {
        const handler = vi.fn();
        const { container } = render(<StatusDock state="idle" onPTT={handler} />);
        fireEvent.click(container.querySelector('.lib-ptt') as Element);
        expect(handler).toHaveBeenCalledOnce();
    });

    it('renders custom ptt slot when provided', () => {
        const { getByText } = render(
            <StatusDock state="idle" ptt={<button type="button">CUSTOM PTT</button>} />,
        );
        expect(getByText('CUSTOM PTT')).toBeDefined();
    });

    it('merges className', () => {
        const { container } = render(<StatusDock state="idle" className="extra" />);
        expect(container.querySelector('.lib-dock')?.classList.contains('extra')).toBe(true);
    });
});
