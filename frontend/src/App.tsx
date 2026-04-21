import React, { useCallback, useEffect, useState } from 'react';
import type { ReactElement } from 'react';
import { OrbCanvas } from './components/OrbCanvas';
import { OrbErrorBoundary } from './components/OrbErrorBoundary';
import { Orb } from './components/hud/Orb';
import { HudTopBar } from './components/HudTopBar';
import { OrbDevMenu } from './components/OrbDevMenu';
import { HudWindows } from './components/hud/HudWindows';
import { SettingsOverlay } from './components/SettingsOverlay';
import { AudioMuteToggle } from './components/AudioMuteToggle';
import { Dock } from './components/Dock';
import { HudHint } from './components/HudHint';
import { HudViewportCorners } from './components/hud/primitives/HudViewportCorners';
import { Reactor } from './components/hud/Reactor';
import {
  WindowManagerProvider,
  useWindowManager,
} from './components/hud/WindowManager';
import { useWebSocket } from './hooks/useWebSocket';
import { useAudioAnalyser } from './hooks/useAudioAnalyser';
import { useMicStream } from './hooks/useMicStream';
import { useConversationMode } from './hooks/useConversationMode';
import { useSettings } from './hooks/useSettings';
import { useAudioEngine } from './hooks/useAudioEngine';
import { useTauriWindowSfx } from './hooks/useTauriWindowSfx';
import { SfxProvider } from './hud/SfxContext';
import { Scene } from './components/hud/Scene';
import type { AppOrbState } from './types';

/**
 * Main JARVIS application component.
 * Fullscreen orb, floating window HUD, top bar, status overlay.
 */
export function App(): ReactElement {
  return (
    <WindowManagerProvider>
      <AppInner />
    </WindowManagerProvider>
  );
}

function AppInner(): ReactElement {
  const [muted, setMuted] = useState(false);
  const [idle, setIdle] = useState(false);
  const [orbOverride, setOrbOverride] = useState<AppOrbState | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [tweaksOpen, setTweaksOpen] = useState(false);
  const settingsHook = useSettings();
  const {
    orbState,
    audioQueue,
    consumeAudio,
    wsRef,
    sendCancelTurn,
    registerStopAudio,
    notifyAudioPlaying,
    connected,
  } = useWebSocket();
  const { analyser, isSpeaking, enqueue, stopAll } = useAudioAnalyser();

  // Register the audio-stop callback so barge_in messages can stop playback.
  useEffect(() => {
    registerStopAudio(stopAll);
  }, [registerStopAudio, stopAll]);

  // Keep the WS hook informed of actual audio playback state so it can hold
  // the orb in `speaking` until the last clip finishes, even after the backend
  // has sent `status=idle`.
  useEffect(() => {
    notifyAudioPlaying(isSpeaking);
  }, [isSpeaking, notifyAudioPlaying]);
  const { resetAll } = useWindowManager();
  const followUp = useConversationMode();

  // SFX engine — manages Web Audio lifecycle and loop state.
  const {
    isMuted: sfxMuted,
    toggleMute: toggleSfxMute,
    playOneShot: sfxPlayOneShot,
  } = useAudioEngine(
    orbOverride ?? (followUp.active && orbState === 'listening' ? 'follow_up' : orbState),
    connected,
    settingsHook.settings.heartbeatEnabled,
  );

  // Wire Tauri window maximize/minimize events to SFX.
  useTauriWindowSfx({ playOneShot: sfxPlayOneShot });

  // Dev-override wins over live pipeline state. When override is null, the
  // orb follows the real pipeline (WebSocket → setOrbState). When a
  // follow-up window is active and no explicit state is set, fold that
  // into the orb state so it picks the `follow_up` visual preset.
  const effectiveOrbState: AppOrbState =
    orbOverride ?? (followUp.active && orbState === 'listening' ? 'follow_up' : orbState);

  // Stream raw PCM audio from the browser mic to the backend via WebSocket.
  // Only pause when explicitly muted. Keep streaming during TTS so the
  // backend barge-in monitor can actually see the user interrupt; echo
  // is handled by browser AEC (echoCancellation: true) plus the
  // backend's post-TTS grace window.
  useMicStream({ wsRef, paused: muted });

  // Feed incoming audio to the audio analyser queue (with per-clip volume and channel).
  useEffect(() => {
    if (audioQueue.length > 0) {
      const item = audioQueue[0];
      enqueue(item.data, item.volume, item.channel);
      consumeAudio();
    }
  }, [audioQueue, enqueue, consumeAudio]);

  // Ctrl+. toggles idle mode
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
    resetAll();
  }, [resetAll]);

  const handleOpenSettings = useCallback(() => {
    setSettingsOpen(true);
  }, []);

  const handleToggleTweaks = useCallback(() => {
    setTweaksOpen((v) => !v);
  }, []);

  // Apply --panel-opacity from settings so all .window elements pick it up
  // without touching individual panel styles.
  const panelOpacityCssVar = { '--panel-opacity': settingsHook.settings.panelOpacity } as React.CSSProperties;

  return (
    <SfxProvider playOneShot={sfxPlayOneShot}>
      <div
        className={`app fixed inset-0 w-screen h-screen overflow-hidden${effectiveOrbState === 'working' ? ' is-working' : ''}`}
        style={{ background: 'var(--bg)', ...panelOpacityCssVar }}
      >
        {/* Viewport corner brackets — fixed to browser window edges, z-index 4 */}
        <HudViewportCorners />

        {/* Animated scene background — z-index 2 */}
        <Scene grid scan stars />

        {/* Reactor halo — standalone 900×900 glow under the orb, z-index 0 */}
        <Reactor />

        {/* Orb — swappable between Classic (Three.js) and Hypermodern (CSS) */}
        {settingsHook.settings.orbVariant === 'hypermodern' ? (
          <div
            className="fixed inset-0 w-screen h-screen"
            style={{ zIndex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', pointerEvents: 'none' }}
          >
            <Orb
              state={effectiveOrbState === 'follow_up' ? 'listening' : effectiveOrbState === 'working' ? 'working' : effectiveOrbState}
              rings
              particles
            />
          </div>
        ) : (
          <OrbErrorBoundary>
            <OrbCanvas
              orbState={effectiveOrbState}
              analyser={analyser}
              mockMode={orbOverride}
              followUp={followUp}
            />
          </OrbErrorBoundary>
        )}

        {/* Floating window HUD — z-index 10 */}
        <HudWindows idle={idle} />

        {/* Top bar — z-index 30 */}
        <HudTopBar
          idle={idle}
          onToggleIdle={() => { setIdle((v) => !v); }}
          onResetLayout={handleResetLayout}
          onOpenSettings={handleOpenSettings}
          tweaksOpen={tweaksOpen}
          onToggleTweaks={handleToggleTweaks}
        />

        {/* Orb dev menu — fixed bottom-left corner, dev-only overlay */}
        <div
          style={{
            position: 'fixed',
            bottom: 10,
            left: 10,
            zIndex: 40,
          }}
        >
          <OrbDevMenu
            override={orbOverride}
            onSet={setOrbOverride}
            onStop={sendCancelTurn}
          />
        </div>

        {/* Mic mute button — inside TopBar right cluster (fixed, sits just left of TopBar controls) */}
        <button
          onClick={() => { setMuted((m) => !m); }}
          aria-label={muted ? 'Unmute microphone' : 'Mute microphone'}
          className="hud-iconbtn"
          style={{
            position: 'fixed',
            top: 4,
            right: 100,
            zIndex: 30,
          }}
        >
          {muted ? (
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <line x1="1" y1="1" x2="23" y2="23" />
              <path d="M9 9v3a3 3 0 0 0 5.12 2.12M15 9.34V4a3 3 0 0 0-5.94-.6" />
              <path d="M17 16.95A7 7 0 0 1 5 12v-2m14 0v2a7 7 0 0 1-.11 1.23" />
              <line x1="12" y1="19" x2="12" y2="23" />
              <line x1="8" y1="23" x2="16" y2="23" />
            </svg>
          ) : (
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
              <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
              <line x1="12" y1="19" x2="12" y2="23" />
              <line x1="8" y1="23" x2="16" y2="23" />
            </svg>
          )}
        </button>

        {/* SFX mute toggle — right of mic mute, inside TopBar right cluster */}
        <div
          style={{
            position: 'fixed',
            top: 4,
            right: 132,
            zIndex: 30,
          }}
        >
          <AudioMuteToggle isMuted={sfxMuted} onToggle={toggleSfxMute} />
        </div>

        {/* Settings overlay — z-index 50, above everything */}
        <SettingsOverlay
          open={settingsOpen}
          onClose={() => { setSettingsOpen(false); }}
          settingsHook={settingsHook}
        />

        {/* Bottom-center dock — PTT button, audio meters, state label + brand */}
        <Dock
          orbState={effectiveOrbState}
          wsRef={wsRef}
          pttEnabled={settingsHook.settings.pushToTalk}
        />

        {/* Bottom-right keyboard hint */}
        <HudHint />
      </div>
    </SfxProvider>
  );
}

export default App;
