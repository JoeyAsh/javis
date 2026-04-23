/**
 * AppShell — top-level layout composer.
 *
 * Owns:
 *   - idle toggle state (Ctrl+. keyboard shortcut).
 *   - settings overlay open state.
 *   - mic-mute state.
 *
 * Mounts HUDShell with orb, topbar, dock, and WindowHost children.
 */

import React, { type ReactElement, useCallback, useEffect, useState } from 'react';
import { HUDShell, Hint } from '@ui';
import { useOrbState } from '@features/orbState';
import { useConversationMode, useMicStream } from '@features/conversation';
import { useSettings } from '@features/settings';
import { useAudioEngine, useTauriWindowSfx, SfxProvider } from '@core/audio';
import { SettingsView } from '@features/settings';
import { TopBar } from './TopBar';
import { Dock } from './Dock';
import { OrbStage } from './OrbStage';
import { WindowHost } from './WindowHost';

// follow_up renders visually as listening
function toDisplayOrbState(
    state: import('@common/types').AppOrbState,
): import('@common/types').AppOrbState {
    if (state === 'follow_up') return 'listening';
    return state;
}

export function AppShell(): ReactElement {
    const [idle, setIdle] = useState(false);
    const [settingsOpen, setSettingsOpen] = useState(false);
    const [micMuted, setMicMuted] = useState(false);

    const settingsHook = useSettings();
    const { state: orbState, connected } = useOrbState();
    useConversationMode();
    useMicStream({ paused: micMuted });

    // ── SFX engine ───────────────────────────────────────────────────────────
    const {
        isMuted: sfxMuted,
        toggleMute: toggleSfxMute,
        playOneShot: sfxPlayOneShot,
        play: sfxPlay,
        stop: sfxStop,
    } = useAudioEngine(orbState, connected, settingsHook.settings.heartbeatEnabled);

    useTauriWindowSfx({ playOneShot: sfxPlayOneShot });

    // ── Keyboard shortcut: Ctrl+. toggles idle ───────────────────────────────
    useEffect(() => {
        const onKey = (e: KeyboardEvent): void => {
            if (e.ctrlKey && e.key === '.') {
                e.preventDefault();
                setIdle((v) => !v);
            }
        };
        window.addEventListener('keydown', onKey);
        return () => {
            window.removeEventListener('keydown', onKey);
        };
    }, []);

    const handleResetLayout = useCallback(() => {
        // Reset is handled inside WindowHost via homeAssignments; no external action needed.
    }, []);

    const handleOpenSettings = useCallback(() => {
        setSettingsOpen(true);
    }, []);

    const shellStyle = {
        '--panel-opacity': settingsHook.settings.panelOpacity,
    } as React.CSSProperties;

    const displayOrbState = toDisplayOrbState(orbState);
    const useThreeJs = settingsHook.settings.orbStyle === 'threejs';

    return (
        <SfxProvider playOneShot={sfxPlayOneShot} play={sfxPlay} stop={sfxStop}>
            <HUDShell
                idle={idle}
                working={orbState === 'working'}
                scene={{ grid: true, stars: true }}
                reactor={!useThreeJs}
                viewportCorners
                orb={
                    <OrbStage
                        orbState={displayOrbState}
                        useThreeJs={useThreeJs}
                        reactor={!useThreeJs}
                    />
                }
                topbar={
                    <TopBar
                        idle={idle}
                        onToggleIdle={() => setIdle((v) => !v)}
                        onResetLayout={handleResetLayout}
                        onOpenSettings={handleOpenSettings}
                        micMuted={micMuted}
                        onToggleMicMute={() => setMicMuted((m) => !m)}
                        sfxMuted={sfxMuted}
                        onToggleSfxMute={toggleSfxMute}
                    />
                }
                dock={
                    <Dock
                        orbState={orbState}
                        pttEnabled={settingsHook.settings.pushToTalk}
                    />
                }
                style={shellStyle}
            >
                <WindowHost idle={idle} orbState={orbState} />

                <SettingsView
                    open={settingsOpen}
                    onClose={() => setSettingsOpen(false)}
                    settingsHook={settingsHook}
                />

                <Hint>
                    PUSH TO TALK · <Hint.Key>SPACE</Hint.Key>
                    {'  '}IDLE · <Hint.Key>CTRL+.</Hint.Key>
                </Hint>
            </HUDShell>
        </SfxProvider>
    );
}

export default AppShell;
