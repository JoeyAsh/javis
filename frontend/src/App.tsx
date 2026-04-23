import React, { type ReactElement, lazy, Suspense, useCallback, useEffect, useState } from 'react';
import { useAudioAnalyser } from './hooks/useAudioAnalyser';
import { useConversationMode } from './hooks/useConversationMode';
import { useMicStream } from './hooks/useMicStream';
import { useSettings } from './hooks/useSettings';
import { useWebSocket } from './hooks/useWebSocket';
import { Hint, HUDShell, CssOrb } from '@ui';
const ThreeOrb = lazy(() => import('./ui/orb/ThreeOrb'));
import { SfxProvider, useAudioEngine, useTauriWindowSfx } from '@core/audio';
import type { AppOrbState } from '@common/types';

// Phase 2 ✅ — migrated to lib WindowManager + contexts/PanelAvailability
import { PanelAvailabilityProvider } from './contexts/PanelAvailability';
import { HudWindowsView } from './views/HudWindowsView';
// Phase 4 ✅ — migrated to views/SettingsView
import { SettingsView } from './views/SettingsView';
// Phase 1b ✅ — migrated to lib TopBar + StatusDock
import { JarvisTopBar } from './views/JarvisTopBar';
import { JarvisDock } from './views/JarvisDock';

/**
 * Main JARVIS application component.
 * Fullscreen orb, floating window HUD, top bar, status overlay.
 */
export function App(): ReactElement {
    return (
        <PanelAvailabilityProvider>
            <AppInner />
        </PanelAvailabilityProvider>
    );
}

/** Map AppOrbState → display state (follow_up renders as listening visually). */
function toDisplayOrbState(state: AppOrbState): AppOrbState {
    if (state === 'follow_up') return 'listening';
    return state;
}

function AppInner(): ReactElement {
    const [muted, setMuted] = useState(false);
    const [idle, setIdle] = useState(false);
    const [settingsOpen, setSettingsOpen] = useState(false);
    const settingsHook = useSettings();
    const {
        orbState,
        audioQueue,
        consumeAudio,
        wsRef,
        registerStopAudio,
        notifyAudioPlaying,
        connected,
    } = useWebSocket();
    const { isSpeaking, enqueue, stopAll } = useAudioAnalyser();
    const followUp = useConversationMode();

    // ── Derived state ────────────────────────────────────────────────────────
    const effectiveOrbState: AppOrbState =
        followUp.active && orbState === 'listening' ? 'follow_up' : orbState;

    // ── Audio stop callback for barge-in ─────────────────────────────────────
    useEffect(() => {
        registerStopAudio(stopAll);
    }, [registerStopAudio, stopAll]);

    // ── Notify WS of audio playback state ────────────────────────────────────
    useEffect(() => {
        notifyAudioPlaying(isSpeaking);
    }, [isSpeaking, notifyAudioPlaying]);

    // ── SFX engine ───────────────────────────────────────────────────────────
    const {
        isMuted: sfxMuted,
        toggleMute: toggleSfxMute,
        playOneShot: sfxPlayOneShot,
        play: sfxPlay,
        stop: sfxStop,
    } = useAudioEngine(effectiveOrbState, connected, settingsHook.settings.heartbeatEnabled);

    useTauriWindowSfx({ playOneShot: sfxPlayOneShot });

    // ── Mic streaming ────────────────────────────────────────────────────────
    useMicStream({ wsRef, paused: muted });

    // ── Audio queue → analyser ───────────────────────────────────────────────
    useEffect(() => {
        if (audioQueue.length > 0) {
            const item = audioQueue[0];
            enqueue(item.data, item.volume, item.channel);
            consumeAudio();
        }
    }, [audioQueue, enqueue, consumeAudio]);

    // ── Keyboard shortcuts ───────────────────────────────────────────────────
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

    // ── Callbacks ────────────────────────────────────────────────────────────
    const handleResetLayout = useCallback(() => {
        // TODO: wire to lib WindowManager reset when Phase 2 exposes a ref/callback
    }, []);

    const handleOpenSettings = useCallback(() => {
        setSettingsOpen(true);
    }, []);

    // ── Panel opacity CSS variable ───────────────────────────────────────────
    const shellStyle = {
        '--panel-opacity': settingsHook.settings.panelOpacity,
    } as React.CSSProperties;

    // ── Orb selection ──────────────────────────────────────────────────────
    const displayOrbState = toDisplayOrbState(effectiveOrbState);
    const useThreeOrb = settingsHook.settings.orbStyle === 'threejs';
    const orbElement = useThreeOrb ? (
        <Suspense key="three" fallback={<CssOrb state={displayOrbState} />}>
            <ThreeOrb state={displayOrbState} />
        </Suspense>
    ) : (
        <CssOrb key="css" state={displayOrbState} />
    );

    return (
        <SfxProvider playOneShot={sfxPlayOneShot} play={sfxPlay} stop={sfxStop}>
            <HUDShell
                idle={idle}
                working={effectiveOrbState === 'working'}
                scene={{ grid: true, stars: true }}
                reactor={!useThreeOrb}
                viewportCorners
                orb={orbElement}
                topbar={
                    <JarvisTopBar
                        idle={idle}
                        onToggleIdle={() => setIdle((v) => !v)}
                        onResetLayout={handleResetLayout}
                        onOpenSettings={handleOpenSettings}
                        micMuted={muted}
                        onToggleMicMute={() => setMuted((m) => !m)}
                        sfxMuted={sfxMuted}
                        onToggleSfxMute={toggleSfxMute}
                    />
                }
                dock={
                    <JarvisDock
                        orbState={effectiveOrbState}
                        wsRef={wsRef}
                        pttEnabled={settingsHook.settings.pushToTalk}
                    />
                }
                style={shellStyle}
            >
                {/* Phase 2 ✅ — lib WindowManager with panel renderers */}
                <HudWindowsView idle={idle} orbState={effectiveOrbState} />

                {/* Settings overlay — z-index 50 */}
                <SettingsView
                    open={settingsOpen}
                    onClose={() => setSettingsOpen(false)}
                    settingsHook={settingsHook}
                />

                {/* Keyboard hint — lib primitive */}
                <Hint>
                    PUSH TO TALK · <Hint.Key>SPACE</Hint.Key>
                    {'  '}IDLE · <Hint.Key>CTRL+.</Hint.Key>
                </Hint>
            </HUDShell>
        </SfxProvider>
    );
}

export default App;
