import React, { useCallback, useEffect, useState } from 'react';
import type { ReactElement } from 'react';
import { OrbCanvas } from './components/OrbCanvas';
import { OrbErrorBoundary } from './components/OrbErrorBoundary';
import { HudTopBar } from './components/HudTopBar';
import { OrbDevMenu } from './components/OrbDevMenu';
import { HudWindows } from './components/hud/HudWindows';
import { SettingsOverlay } from './components/SettingsOverlay';
import { PushToTalkButton } from './components/PushToTalkButton';
import {
  WindowManagerProvider,
  useWindowManager,
} from './components/hud/WindowManager';
import { useWebSocket } from './hooks/useWebSocket';
import { useAudioAnalyser } from './hooks/useAudioAnalyser';
import { useMicStream } from './hooks/useMicStream';
import { useConversationMode } from './hooks/useConversationMode';
import { useSettings } from './hooks/useSettings';
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
  const settingsHook = useSettings();
  const {
    orbState,
    audioQueue,
    consumeAudio,
    wsRef,
    sendCancelTurn,
    registerStopAudio,
    notifyAudioPlaying,
    currentToolSummary,
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

  // Feed incoming audio to the audio analyser queue (with per-clip volume).
  useEffect(() => {
    if (audioQueue.length > 0) {
      const item = audioQueue[0];
      enqueue(item.data, item.volume);
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

  const statusLabel =
    effectiveOrbState === 'listening'
      ? 'listening...'
      : effectiveOrbState === 'thinking'
        ? 'thinking...'
        : effectiveOrbState === 'speaking'
          ? 'speaking...'
          : effectiveOrbState === 'follow_up'
            ? 'follow-up...'
            : effectiveOrbState === 'working'
              ? (currentToolSummary ?? 'working...')
              : '';

  // Apply --panel-opacity from settings so all .window elements pick it up
  // without touching individual panel styles.
  const panelOpacityCssVar = { '--panel-opacity': settingsHook.settings.panelOpacity } as React.CSSProperties;

  return (
    <div
      className="fixed inset-0 w-screen h-screen overflow-hidden"
      style={{ background: 'var(--bg)', ...panelOpacityCssVar }}
    >
      {/* Orb canvas — backdrop, z-index 0 */}
      <OrbErrorBoundary>
        <OrbCanvas
          orbState={effectiveOrbState}
          analyser={analyser}
          mockMode={orbOverride}
          followUp={followUp}
        />
      </OrbErrorBoundary>

      {/* Floating window HUD — z-index 10 */}
      <HudWindows idle={idle} />

      {/* Top bar — z-index 30 */}
      <HudTopBar
        idle={idle}
        onToggleIdle={() => setIdle((v) => !v)}
        onResetLayout={handleResetLayout}
        onOpenSettings={handleOpenSettings}
      />

      {/* Orb dev menu — forced state override for testing + STOP button */}
      <div
        style={{
          position: 'fixed',
          top: 4,
          right: 240,
          zIndex: 40,
        }}
      >
        <OrbDevMenu
          override={orbOverride}
          onSet={setOrbOverride}
          onStop={sendCancelTurn}
        />
      </div>

      {/* Mute button — top right, nudged left of the top-bar controls */}
      <button
        onClick={() => setMuted((m) => !m)}
        aria-label={muted ? 'Unmute microphone' : 'Mute microphone'}
        style={{
          position: 'fixed',
          top: 4,
          right: 180,
          width: 28,
          height: 28,
          zIndex: 40,
          background: 'rgba(13,13,20,0.6)',
          border: '1px solid var(--border)',
          borderRadius: 4,
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: muted ? 'var(--text-muted)' : 'var(--accent)',
          transition: 'color 200ms, border-color 200ms',
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

      {/* Settings overlay — z-index 50, above everything */}
      <SettingsOverlay
        open={settingsOpen}
        onClose={() => { setSettingsOpen(false); }}
        settingsHook={settingsHook}
      />

      {/* Push-to-Talk button — rendered only when enabled in settings */}
      <PushToTalkButton
        enabled={settingsHook.settings.pushToTalk}
        wsRef={wsRef}
      />

      {/* Bottom center: status text + JARVIS label */}
      <div
        style={{
          position: 'fixed',
          bottom: 16,
          left: 0,
          right: 0,
          zIndex: 20,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 4,
          pointerEvents: 'none',
        }}
      >
        <span
          style={{
            fontSize: 11,
            color: 'var(--text-secondary)',
            fontFamily: 'var(--font)',
            letterSpacing: '0.1em',
            minHeight: '1.4em',
            transition: 'opacity 200ms',
            opacity: statusLabel ? 1 : 0,
          }}
        >
          {statusLabel}
        </span>
        <span
          style={{
            fontSize: 9,
            color: 'var(--text-muted)',
            fontFamily: 'var(--font)',
            textTransform: 'uppercase',
            letterSpacing: '6px',
          }}
        >
          JARVIS
        </span>
      </div>
    </div>
  );
}

export default App;
