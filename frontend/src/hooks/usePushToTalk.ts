/**
 * usePushToTalk — push-to-talk audio capture logic.
 *
 * Extracts the mic capture pipeline from PushToTalkButton so the Dock
 * component can render the full prototype UI while keeping the WebSocket
 * integration in one place.
 *
 * Usage:
 *   const { pttState, handlePressStart, handlePressEnd } = usePushToTalk({ wsRef });
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import type React from 'react';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type PttState = 'idle' | 'holding' | 'flash';

export interface UsePushToTalkOptions {
  /** Raw WebSocket ref — binary PCM frames are sent directly. */
  wsRef: React.RefObject<WebSocket | null>;
}

export interface UsePushToTalkReturn {
  pttState: PttState;
  handlePressStart: () => void;
  handlePressEnd: () => void;
}

// ---------------------------------------------------------------------------
// Audio helpers
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
// Hook
// ---------------------------------------------------------------------------

export function usePushToTalk({ wsRef }: UsePushToTalkOptions): UsePushToTalkReturn {
  const [pttState, setPttState] = useState<PttState>('idle');

  const audioCtxRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  // eslint-disable-next-line @typescript-eslint/no-deprecated
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const sendingRef = useRef(false);
  const flashTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Cleanup on unmount
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

  return { pttState, handlePressStart, handlePressEnd };
}
