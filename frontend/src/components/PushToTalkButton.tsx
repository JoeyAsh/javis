/**
 * PushToTalkButton — hold-to-record mic button positioned near the orb.
 *
 * States:
 *   idle    — muted mic icon, no pulse
 *   holding — active pulse ring, accent glow
 *   flash   — brief bright flash on release (300ms)
 *
 * Audio is streamed through the existing WebSocket path exactly like the
 * wake-word-triggered stream: raw Int16 PCM frames sent as binary WS messages.
 * The hook controls a pausedRef so we only emit frames while the button is held.
 *
 * PTT is only rendered when `enabled` is true (toggled in Settings → Audio).
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import type { ReactElement } from 'react';
import type React from 'react';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type PttState = 'idle' | 'holding' | 'flash';

export interface PushToTalkButtonProps {
  /** When false, the button is not rendered. */
  enabled: boolean;
  /** Raw WebSocket ref — PTT sends binary PCM frames directly. */
  wsRef: React.RefObject<WebSocket | null>;
}

// ---------------------------------------------------------------------------
// Audio capture helpers (mirror of useMicStream but push-to-talk controlled)
// ---------------------------------------------------------------------------

function floatToInt16(float32: Float32Array, sourceSampleRate: number): Int16Array {
  const targetSampleRate = 16000;
  let samples: Float32Array;

  if (sourceSampleRate !== targetSampleRate) {
    const ratio = sourceSampleRate / targetSampleRate;
    const outputLength = Math.floor(float32.length / ratio);
    samples = new Float32Array(outputLength);
    for (let i = 0; i < outputLength; i++) {
      const srcIdx = Math.floor(i * ratio);
      samples[i] = float32[srcIdx];
    }
  } else {
    samples = float32;
  }

  const int16 = new Int16Array(samples.length);
  for (let i = 0; i < samples.length; i++) {
    const clamped = Math.max(-1, Math.min(1, samples[i]));
    int16[i] = clamped < 0 ? clamped * 32768 : clamped * 32767;
  }
  return int16;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function PushToTalkButton({ enabled, wsRef }: PushToTalkButtonProps): ReactElement | null {
  const [pttState, setPttState] = useState<PttState>('idle');

  // Audio pipeline refs — created lazily on first hold, kept alive for the
  // session so subsequent presses incur no setup latency.
  const audioCtxRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  // eslint-disable-next-line @typescript-eslint/no-deprecated
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const sendingRef = useRef(false);
  const flashTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Clean up audio on unmount
  useEffect(() => {
    return () => {
      if (flashTimerRef.current) clearTimeout(flashTimerRef.current);
      processorRef.current?.disconnect();
      sourceRef.current?.disconnect();
      streamRef.current?.getTracks().forEach((t) => { t.stop(); });
      audioCtxRef.current?.close();
    };
  }, []);

  const startCapture = useCallback(async () => {
    // Init AudioContext + stream lazily on first press.
    if (!audioCtxRef.current || audioCtxRef.current.state === 'closed') {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            channelCount: 1,
            sampleRate: 16000,
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
          },
        });
        const ctx = new AudioContext({ sampleRate: 16000 });
        // eslint-disable-next-line @typescript-eslint/no-deprecated
        const processor = ctx.createScriptProcessor(4096, 1, 1);
        const source = ctx.createMediaStreamSource(stream);

        processor.onaudioprocess = (event: AudioProcessingEvent) => {
          if (!sendingRef.current) return;
          if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;

          const float32 = event.inputBuffer.getChannelData(0);
          const int16 = floatToInt16(float32, event.inputBuffer.sampleRate);
          wsRef.current.send(int16.buffer as ArrayBuffer);
        };

        const silentGain = ctx.createGain();
        silentGain.gain.value = 0;
        source.connect(processor);
        processor.connect(silentGain);
        silentGain.connect(ctx.destination);

        audioCtxRef.current = ctx;
        streamRef.current = stream;
        processorRef.current = processor;
        sourceRef.current = source;
      } catch (err) {
        console.error('[PTT] Failed to start mic capture:', err);
        return;
      }
    }

    if (audioCtxRef.current.state === 'suspended') {
      await audioCtxRef.current.resume();
    }

    sendingRef.current = true;
  }, [wsRef]);

  const stopCapture = useCallback(() => {
    sendingRef.current = false;
  }, []);

  const handlePressStart = useCallback(() => {
    if (flashTimerRef.current) {
      clearTimeout(flashTimerRef.current);
      flashTimerRef.current = null;
    }
    setPttState('holding');
    void startCapture();
  }, [startCapture]);

  const handlePressEnd = useCallback(() => {
    stopCapture();
    setPttState('flash');
    flashTimerRef.current = setTimeout(() => {
      setPttState('idle');
      flashTimerRef.current = null;
    }, 300);
  }, [stopCapture]);

  if (!enabled) return null;

  const isHolding = pttState === 'holding';
  const isFlash = pttState === 'flash';

  return (
    <div
      style={{
        position: 'fixed',
        bottom: 72,
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: 20,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 6,
        pointerEvents: 'auto',
      }}
    >
      {/* Pulse ring — visible while holding */}
      {isHolding && (
        <div
          aria-hidden="true"
          style={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            width: 64,
            height: 64,
            borderRadius: '50%',
            border: '1px solid var(--accent)',
            animation: 'ptt-ring 900ms ease-out infinite',
            pointerEvents: 'none',
          }}
        />
      )}

      <button
        type="button"
        aria-label={isHolding ? 'Recording — release to stop' : 'Push to talk'}
        aria-pressed={isHolding}
        onMouseDown={handlePressStart}
        onMouseUp={handlePressEnd}
        onMouseLeave={handlePressEnd}
        onTouchStart={(e) => {
          e.preventDefault();
          handlePressStart();
        }}
        onTouchEnd={(e) => {
          e.preventDefault();
          handlePressEnd();
        }}
        style={{
          width: 40,
          height: 40,
          borderRadius: 2,
          border: `1px solid ${isHolding ? 'var(--accent)' : isFlash ? 'var(--accent-bright)' : 'var(--border)'}`,
          background: isHolding
            ? 'rgba(76,168,232,0.2)'
            : isFlash
              ? 'rgba(110,196,255,0.3)'
              : 'rgba(13,13,20,0.75)',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: isHolding ? 'var(--accent)' : isFlash ? 'var(--accent-bright)' : 'var(--text-muted)',
          boxShadow: isHolding ? 'var(--glow-strong)' : isFlash ? 'var(--glow)' : 'none',
          transition: 'background 150ms, border-color 150ms, color 150ms, box-shadow 150ms',
          userSelect: 'none',
          WebkitUserSelect: 'none',
        }}
      >
        <svg
          width="16"
          height="16"
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
      </button>

      <span
        style={{
          fontSize: 8,
          letterSpacing: '0.12em',
          textTransform: 'uppercase',
          fontFamily: 'var(--font)',
          color: isHolding ? 'var(--accent)' : 'var(--text-muted)',
          transition: 'color 150ms',
          pointerEvents: 'none',
        }}
      >
        {isHolding ? 'REC' : 'PTT'}
      </span>
    </div>
  );
}

export default PushToTalkButton;
