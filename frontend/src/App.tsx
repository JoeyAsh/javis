import { useEffect, useState } from 'react';
import { OrbCanvas } from './components/OrbCanvas';
import { OrbErrorBoundary } from './components/OrbErrorBoundary';
import { useWebSocket } from './hooks/useWebSocket';
import { useAudioAnalyser } from './hooks/useAudioAnalyser';
import { useMicStream } from './hooks/useMicStream';

/**
 * Main JARVIS application component.
 * Fullscreen orb, mute button, minimal status overlay.
 */
export function App() {
  const [muted, setMuted] = useState(false);
  const { orbState, setOrbState, audioQueue, consumeAudio, wsRef } = useWebSocket();
  const { analyser, isSpeaking, enqueue } = useAudioAnalyser();

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

  const statusLabel =
    orbState === 'listening'
      ? 'listening...'
      : orbState === 'thinking'
        ? 'thinking...'
        : orbState === 'speaking'
          ? 'speaking...'
          : '';

  return (
    <div className="fixed inset-0 w-screen h-screen overflow-hidden" style={{ background: 'var(--bg)' }}>
      <OrbErrorBoundary>
        <OrbCanvas orbState={orbState} analyser={analyser} />
      </OrbErrorBoundary>

      {/* Mute button — top right */}
      <button
        onClick={() => setMuted((m) => !m)}
        aria-label={muted ? 'Unmute microphone' : 'Mute microphone'}
        style={{
          position: 'fixed',
          top: 20,
          right: 20,
          width: 36,
          height: 36,
          zIndex: 10,
          background: 'transparent',
          border: '1px solid rgba(255,255,255,0.15)',
          borderRadius: 8,
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          backdropFilter: 'blur(8px)',
          WebkitBackdropFilter: 'blur(8px)',
          color: muted ? 'rgba(255,255,255,0.35)' : 'var(--accent)',
          transition: 'color 200ms, border-color 200ms',
        }}
      >
        {muted ? (
          // Mic-off icon
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="1" y1="1" x2="23" y2="23" />
            <path d="M9 9v3a3 3 0 0 0 5.12 2.12M15 9.34V4a3 3 0 0 0-5.94-.6" />
            <path d="M17 16.95A7 7 0 0 1 5 12v-2m14 0v2a7 7 0 0 1-.11 1.23" />
            <line x1="12" y1="19" x2="12" y2="23" />
            <line x1="8" y1="23" x2="16" y2="23" />
          </svg>
        ) : (
          // Mic icon
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
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
          bottom: 40,
          left: 0,
          right: 0,
          zIndex: 10,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 8,
          pointerEvents: 'none',
        }}
      >
        <span
          style={{
            fontSize: 13,
            color: 'rgba(255,255,255,0.45)',
            fontFamily: 'system-ui, -apple-system, sans-serif',
            letterSpacing: '0.05em',
            minHeight: '1.4em',
            transition: 'opacity 200ms',
            opacity: statusLabel ? 1 : 0,
          }}
        >
          {statusLabel}
        </span>
        <span
          style={{
            fontSize: 10,
            color: 'rgba(255,255,255,0.2)',
            fontFamily: 'system-ui, -apple-system, sans-serif',
            textTransform: 'uppercase',
            letterSpacing: '4px',
          }}
        >
          JARVIS
        </span>
      </div>
    </div>
  );
}

export default App;
