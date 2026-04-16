import { useCallback, useEffect, useState } from 'react';
import type { ReactElement } from 'react';
import { OrbCanvas } from './components/OrbCanvas';
import { OrbErrorBoundary } from './components/OrbErrorBoundary';
import { HudTopBar } from './components/HudTopBar';
import { OrbDevMenu } from './components/OrbDevMenu';
import { HudWindows } from './components/hud/HudWindows';
import {
  WindowManagerProvider,
  useWindowManager,
} from './components/hud/WindowManager';
import { useWebSocket } from './hooks/useWebSocket';
import { useAudioAnalyser } from './hooks/useAudioAnalyser';
import { useMicStream } from './hooks/useMicStream';
import type { OrbState } from './types';

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
  const [orbOverride, setOrbOverride] = useState<OrbState | null>(null);
  const { orbState, setOrbState, audioQueue, consumeAudio, wsRef } = useWebSocket();
  const { analyser, isSpeaking, enqueue } = useAudioAnalyser();
  const { resetAll } = useWindowManager();

  // Dev-override wins over live pipeline state. When override is null, the
  // orb follows the real pipeline (WebSocket → setOrbState).
  const effectiveOrbState: OrbState = orbOverride ?? orbState;

  // Stream raw PCM audio from the browser mic to the backend via WebSocket.
  // Paused while JARVIS is speaking (to prevent feedback) or while muted.
  useMicStream({ wsRef, paused: muted || isSpeaking });

  // Feed incoming audio to the audio analyser queue
  useEffect(() => {
    if (audioQueue.length > 0) {
      enqueue(audioQueue[0]);
      consumeAudio();
    }
  }, [audioQueue, enqueue, consumeAudio]);

  // When audio finishes playing, transition orb back to idle
  useEffect(() => {
    if (!isSpeaking && orbState === 'speaking') {
      setOrbState('idle');
    }
  }, [isSpeaking, orbState, setOrbState]);

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
    // Stub: settings modal not built yet.
    // eslint-disable-next-line no-alert
    alert('Settings modal — not yet implemented.');
  }, []);

  const statusLabel =
    effectiveOrbState === 'listening'
      ? 'listening...'
      : effectiveOrbState === 'thinking'
        ? 'thinking...'
        : effectiveOrbState === 'speaking'
          ? 'speaking...'
          : '';

  return (
    <div
      className="fixed inset-0 w-screen h-screen overflow-hidden"
      style={{ background: 'var(--bg)' }}
    >
      {/* Orb canvas — backdrop, z-index 0 */}
      <OrbErrorBoundary>
        <OrbCanvas
          orbState={effectiveOrbState}
          analyser={analyser}
          mockMode={orbOverride}
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

      {/* Orb dev menu — forced state override for testing */}
      <div
        style={{
          position: 'fixed',
          top: 4,
          right: 240,
          zIndex: 40,
        }}
      >
        <OrbDevMenu override={orbOverride} onSet={setOrbOverride} />
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
