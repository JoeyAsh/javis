/**
 * SettingsOverlay — Vitest + RTL tests.
 *
 * Tests cover:
 *   - Renders nothing when open=false
 *   - Renders dialog when open=true
 *   - Closes on Escape key
 *   - Closes on close-button click
 *   - Navigation between sections
 *   - Persona section shows ownership note
 *   - Display section has opacity slider
 *   - Voice section has autospeak toggle
 *   - Audio section shows mic denied message
 */
import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { SettingsOverlay } from '../SettingsOverlay';
import type { UseSettingsReturn } from '../../hooks/useSettings';

// ---------------------------------------------------------------------------
// Mock localStorage
// ---------------------------------------------------------------------------

beforeEach(() => {
    vi.spyOn(Storage.prototype, 'getItem').mockReturnValue(null);
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {});
});

afterEach(() => {
    vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Mock navigator.mediaDevices — not available in jsdom
// ---------------------------------------------------------------------------

beforeEach(() => {
    Object.defineProperty(globalThis.navigator, 'mediaDevices', {
        writable: true,
        configurable: true,
        value: {
            getUserMedia: vi.fn().mockRejectedValue(new Error('NotAllowedError')),
            enumerateDevices: vi.fn().mockResolvedValue([]),
        },
    });
});

// ---------------------------------------------------------------------------
// Fake settingsHook
// ---------------------------------------------------------------------------

function makeSettingsHook(overrides: Partial<UseSettingsReturn> = {}): UseSettingsReturn {
    return {
        settings: {
            panelOpacity: 1.0,
            autoSpeakClaude: true,
            pushToTalk: false,
            micDeviceId: '',
            heartbeatEnabled: false,
            orbStyle: 'css',
        },
        setPanelOpacity: vi.fn(),
        setAutoSpeakClaude: vi.fn(),
        setPushToTalk: vi.fn(),
        setMicDeviceId: vi.fn(),
        setHeartbeatEnabled: vi.fn(),
        setOrbStyle: vi.fn(),
        ...overrides,
    };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('SettingsOverlay', () => {
    it('renders nothing when open=false', () => {
        const { container } = render(
            <SettingsOverlay open={false} onClose={vi.fn()} settingsHook={makeSettingsHook()} />,
        );
        expect(container.firstChild).toBeNull();
    });

    it('renders dialog when open=true', () => {
        render(<SettingsOverlay open onClose={vi.fn()} settingsHook={makeSettingsHook()} />);
        expect(screen.getByRole('dialog')).toBeTruthy();
        expect(screen.getByText('Settings')).toBeTruthy();
    });

    it('calls onClose when Escape is pressed', () => {
        const onClose = vi.fn();
        render(<SettingsOverlay open onClose={onClose} settingsHook={makeSettingsHook()} />);
        fireEvent.keyDown(window, { key: 'Escape' });
        expect(onClose).toHaveBeenCalledOnce();
    });

    it('calls onClose when close button is clicked', () => {
        const onClose = vi.fn();
        render(<SettingsOverlay open onClose={onClose} settingsHook={makeSettingsHook()} />);
        const closeBtn = screen.getByLabelText('Close settings');
        fireEvent.click(closeBtn);
        expect(onClose).toHaveBeenCalledOnce();
    });

    it('navigates to Persona section and shows ownership note', () => {
        render(<SettingsOverlay open onClose={vi.fn()} settingsHook={makeSettingsHook()} />);
        // Click Persona nav button
        const navButtons = screen.getAllByRole('button');
        const personaBtn = navButtons.find((b) => b.textContent === 'Persona');
        expect(personaBtn).toBeTruthy();
        fireEvent.click(personaBtn!);
        expect(screen.getByText(/Johannes Aschenbrenner/)).toBeTruthy();
    });

    it('navigates to Display section and shows opacity slider', () => {
        render(<SettingsOverlay open onClose={vi.fn()} settingsHook={makeSettingsHook()} />);
        const navButtons = screen.getAllByRole('button');
        const displayBtn = navButtons.find((b) => b.textContent === 'Display');
        expect(displayBtn).toBeTruthy();
        fireEvent.click(displayBtn!);
        const slider = screen.getByLabelText(/panel opacity/i);
        expect(slider).toBeTruthy();
        expect((slider as HTMLInputElement).type).toBe('range');
    });

    it('navigates to Voice section and shows autospeak toggle', () => {
        render(<SettingsOverlay open onClose={vi.fn()} settingsHook={makeSettingsHook()} />);
        const navButtons = screen.getAllByRole('button');
        const voiceBtn = navButtons.find((b) => b.textContent === 'Voice');
        expect(voiceBtn).toBeTruthy();
        fireEvent.click(voiceBtn!);
        expect(screen.getByText(/Nachrichten automatisch vorlesen/i)).toBeTruthy();
    });

    it('shows mic denied message when getUserMedia fails', async () => {
        render(<SettingsOverlay open onClose={vi.fn()} settingsHook={makeSettingsHook()} />);
        // Audio tab is shown by default; wait for async effect to resolve
        await act(async () => {
            await new Promise<void>((resolve) => setTimeout(resolve, 50));
        });
        expect(screen.getByText(/permission denied/i)).toBeTruthy();
    });

    it('opacity slider fires setPanelOpacity on change', () => {
        const setPanelOpacity = vi.fn();
        render(
            <SettingsOverlay
                open
                onClose={vi.fn()}
                settingsHook={makeSettingsHook({ setPanelOpacity })}
            />,
        );
        const navButtons = screen.getAllByRole('button');
        const displayBtn = navButtons.find((b) => b.textContent === 'Display');
        fireEvent.click(displayBtn!);
        const slider = screen.getByLabelText(/panel opacity/i);
        fireEvent.change(slider, { target: { value: '0.75' } });
        expect(setPanelOpacity).toHaveBeenCalledWith(0.75);
    });

    it('autospeak toggle fires setAutoSpeakClaude on click', () => {
        const setAutoSpeakClaude = vi.fn();
        render(
            <SettingsOverlay
                open
                onClose={vi.fn()}
                settingsHook={makeSettingsHook({ setAutoSpeakClaude })}
            />,
        );
        // Navigate to Voice tab
        const navButtons = screen.getAllByRole('button');
        const voiceBtn = navButtons.find((b) => b.textContent === 'Voice');
        fireEvent.click(voiceBtn!);
        // Toggle buttons use role="switch"; find the first one
        const [toggleBtn] = screen.getAllByRole('switch');
        expect(toggleBtn).toBeTruthy();
        fireEvent.click(toggleBtn);
        expect(setAutoSpeakClaude).toHaveBeenCalledWith(false); // was true, toggled to false
    });
});
