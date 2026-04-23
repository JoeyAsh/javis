/**
 * SettingsView — Vitest + RTL tests (Batch 3b).
 *
 * Tests cover:
 *   - Renders null when open=false
 *   - Renders dialog when open=true
 *   - ESC closes the modal
 *   - Backdrop click closes the modal
 *   - Section tab click switches section
 *   - Toggle flips state on click
 *   - RepositoriesSection mock (RTK Query)
 */
import { act, fireEvent, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWithProviders } from '@test/renderWithProviders';
import { SettingsView } from '../components/SettingsView';
import type { UseSettingsReturn } from '../hooks/useSettings.types';

// ---------------------------------------------------------------------------
// Mock SfxContext — useSfx is called in SettingsView
// ---------------------------------------------------------------------------
vi.mock('@core/audio', async (importOriginal) => {
    const original = await importOriginal<typeof import('@core/audio')>();
    return {
        ...original,
        useSfx: () => ({ playOneShot: vi.fn(), play: vi.fn(), stop: vi.fn() }),
    };
});

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

describe('SettingsView', () => {
    it('renders null when open=false', () => {
        const { container } = renderWithProviders(
            <SettingsView open={false} onClose={vi.fn()} settingsHook={makeSettingsHook()} />,
        );
        expect(container.firstChild).toBeNull();
    });

    it('renders dialog when open=true', () => {
        renderWithProviders(
            <SettingsView open onClose={vi.fn()} settingsHook={makeSettingsHook()} />,
        );
        expect(screen.getByRole('dialog')).toBeTruthy();
        expect(screen.getByText('Settings')).toBeTruthy();
    });

    it('calls onClose when Escape is pressed', () => {
        const onClose = vi.fn();
        renderWithProviders(
            <SettingsView open onClose={onClose} settingsHook={makeSettingsHook()} />,
        );
        fireEvent.keyDown(window, { key: 'Escape' });
        expect(onClose).toHaveBeenCalledOnce();
    });

    it('calls onClose when close button is clicked', () => {
        const onClose = vi.fn();
        renderWithProviders(
            <SettingsView open onClose={onClose} settingsHook={makeSettingsHook()} />,
        );
        const closeBtn = screen.getByLabelText('Close settings');
        fireEvent.click(closeBtn);
        expect(onClose).toHaveBeenCalledOnce();
    });

    it('navigates to Persona section on tab click and shows owner note', () => {
        renderWithProviders(
            <SettingsView open onClose={vi.fn()} settingsHook={makeSettingsHook()} />,
        );
        const personaBtn = screen.getByText('Persona');
        fireEvent.click(personaBtn);
        expect(screen.getByText(/Johannes Aschenbrenner/)).toBeTruthy();
    });

    it('navigates to Display section and shows opacity slider', () => {
        renderWithProviders(
            <SettingsView open onClose={vi.fn()} settingsHook={makeSettingsHook()} />,
        );
        fireEvent.click(screen.getByText('Display'));
        const slider = screen.getByLabelText(/panel opacity/i);
        expect(slider).toBeTruthy();
        expect((slider as HTMLInputElement).type).toBe('range');
    });

    it('navigates to Voice section and shows autospeak toggle', () => {
        renderWithProviders(
            <SettingsView open onClose={vi.fn()} settingsHook={makeSettingsHook()} />,
        );
        fireEvent.click(screen.getByText('Voice'));
        expect(screen.getByText(/Nachrichten automatisch vorlesen/i)).toBeTruthy();
    });

    it('shows mic denied message when getUserMedia fails', async () => {
        renderWithProviders(
            <SettingsView open onClose={vi.fn()} settingsHook={makeSettingsHook()} />,
        );
        // Audio tab is default; wait for async effect to resolve
        await act(async () => {
            await new Promise<void>((resolve) => setTimeout(resolve, 50));
        });
        expect(screen.getByText(/permission denied/i)).toBeTruthy();
    });

    it('autospeak toggle fires setAutoSpeakClaude on click', () => {
        const setAutoSpeakClaude = vi.fn();
        renderWithProviders(
            <SettingsView
                open
                onClose={vi.fn()}
                settingsHook={makeSettingsHook({ setAutoSpeakClaude })}
            />,
        );
        fireEvent.click(screen.getByText('Voice'));
        const [toggleBtn] = screen.getAllByRole('switch');
        fireEvent.click(toggleBtn);
        expect(setAutoSpeakClaude).toHaveBeenCalledWith(false); // was true → toggled to false
    });

    it('opacity slider fires setPanelOpacity on change', () => {
        const setPanelOpacity = vi.fn();
        renderWithProviders(
            <SettingsView
                open
                onClose={vi.fn()}
                settingsHook={makeSettingsHook({ setPanelOpacity })}
            />,
        );
        fireEvent.click(screen.getByText('Display'));
        const slider = screen.getByLabelText(/panel opacity/i);
        fireEvent.change(slider, { target: { value: '0.75' } });
        expect(setPanelOpacity).toHaveBeenCalledWith(0.75);
    });
});
