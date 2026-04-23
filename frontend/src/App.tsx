import React, { type ReactElement, lazy, Suspense, useCallback, useEffect, useState } from 'react';
import { useAudioAnalyser } from './hooks/useAudioAnalyser';
import { useSettings } from '@features/settings';
import { useWebSocket } from './hooks/useWebSocket';
import { Hint, HUDShell, CssOrb } from '@ui';
const ThreeOrb = lazy(() => import('./ui/orb/ThreeOrb'));
import { SfxProvider, useAudioEngine, useTauriWindowSfx } from '@core/audio';
import type { AppOrbState } from '@common/types';

// Phase 2 ✅ — migrated to lib WindowManager + contexts/PanelAvailability
import { PanelAvailabilityProvider } from './contexts/PanelAvailability';
import { HudWindowsView } from './views/HudWindowsView';
// Batch 3b ✅ — migrated to features/settings
import { SettingsView } from '@features/settings';
// Phase 1b ✅ — migrated to lib TopBar + StatusDock
import { JarvisTopBar } from './views/JarvisTopBar';
import { JarvisDock } from './views/JarvisDock';

// Batch 3a ✅ — orbState + conversation features
import { useOrbState } from '@features/orbState';
import { useConversationMode, useMicStream } from '@features/conversation';

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
        audioQueue,
        consumeAudio,
        registerStopAudio,
        notifyAudioPlaying,
    } = useWebSocket();
    const { isSpeaking, enqueue, stopAll } = useAudioAnalyser();

    // Batch 3a — orb state + connection from feature slice
    const { state: orbState, connected } = useOrbState();

    // Batch 3a — follow-up mode from feature slice
    // (selectAppOrbState in orbStateSelectors handles 'working' priority;
    //  the follow_up → listening visual mapping stays in toDisplayOrbState)
    useConversationMode();

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
    } = useAudioEngine(orbState, connected, settingsHook.settings.heartbeatEnabled);

    useTauriWindowSfx({ playOneShot: sfxPlayOneShot });

    // ── Mic streaming ────────────────────────────────────────────────────────
    useMicStream({ paused: muted });

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
    const displayOrbState = toDisplayOrbState(orbState);
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
                working={orbState === 'working'}
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
                        orbState={orbState}
                        pttEnabled={settingsHook.settings.pushToTalk}
                    />
                }
                style={shellStyle}
            >
                {/* Phase 2 ✅ — lib WindowManager with panel renderers */}
                <HudWindowsView idle={idle} orbState={orbState} />

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
