import { useEffect, useRef } from 'react';
import { wsClient } from '@core/websocket/wsClient';
import type { MicSessionState, UseMicStreamOptions, UseMicStreamReturn } from './useMicStream.types';

/**
 * Hook that captures raw microphone audio in the browser and streams
 * it to the JARVIS backend as binary Int16 PCM frames at 16 kHz mono.
 *
 * Audio path:
 *   getUserMedia → AudioContext (16 kHz) → ScriptProcessorNode (4096 samples)
 *   → downsample to 16 kHz mono Int16 → wsClient.sendBinary
 *
 * When `paused` is true no frames are sent (used while JARVIS is speaking
 * to prevent feedback).
 *
 * Uses a module-level singleton to be idempotent under React 18 StrictMode
 * (mount → cleanup-unmount → remount). A refCount guards start/stop so the
 * AudioContext is created once per tab lifetime, not once per render cycle.
 */

// ---------------------------------------------------------------------------
// Module-level singleton — mirrors wsClient singleton pattern
// ---------------------------------------------------------------------------

const session: MicSessionState = {
    audioCtx: null,
    sourceNode: null,
    processorNode: null,
    silentGain: null,
    stream: null,
    unlockHandler: null,
    starting: false,
    refCount: 0,
    firstFrameLogged: false,
    pausedRef: null,
};

async function startMicSession(pausedRef: React.RefObject<boolean>): Promise<void> {
    // Idempotent: if already running or starting, bail out immediately.
    if (session.audioCtx !== null || session.starting) {
        return;
    }

    session.starting = true;
    // Store the ref so onaudioprocess can read it from the singleton.
    session.pausedRef = pausedRef;

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

        // If the session was torn down while getUserMedia was in-flight, discard.
        if (session.starting === false) {
            stream.getTracks().forEach((t) => t.stop());
            return;
        }

        session.stream = stream;

        // Request 16 kHz explicitly; browser may not honour it — we downsample
        // in the processor if needed.
        const audioCtx = new AudioContext({ sampleRate: 16000 });
        session.audioCtx = audioCtx;

        // AudioContext starts in 'suspended' state under the autoplay policy.
        // Resume immediately — the just-completed getUserMedia permission grant
        // counts as a user gesture, so this should succeed without further input.
        if (audioCtx.state === 'suspended') {
            try {
                await audioCtx.resume();
            } catch (err) {
                console.warn(
                    '[useMicStream] AudioContext resume failed; will retry on next user gesture:',
                    err,
                );
            }
        }

        session.sourceNode = audioCtx.createMediaStreamSource(stream);

        // bufferSize=4096 gives ~256 ms at 16 kHz — a good balance between
        // latency and CPU. Use mono (1 channel).
        // eslint-disable-next-line @typescript-eslint/no-deprecated
        session.processorNode = audioCtx.createScriptProcessor(4096, 1, 1);

        session.processorNode.onaudioprocess = (event: AudioProcessingEvent) => {
            // Read paused state from the singleton's pausedRef slot.
            if (session.pausedRef?.current) return;

            const inputBuffer = event.inputBuffer;
            const float32 = inputBuffer.getChannelData(0);

            // Convert float32 [-1, 1] → int16 [-32768, 32767]
            const int16 = floatToInt16(float32, inputBuffer.sampleRate);

            if (!session.firstFrameLogged) {
                console.info(
                    `[useMicStream] First PCM frame: ${int16.length} samples, sr=${inputBuffer.sampleRate}, ctxState=${session.audioCtx?.state}`,
                );
                session.firstFrameLogged = true;
            }
            wsClient.sendBinary(int16.buffer as ArrayBuffer);
        };

        session.sourceNode.connect(session.processorNode);

        // Connect to destination with zero gain so the browser doesn't echo
        // the mic back to the speakers but still runs the graph.
        const silentGain = audioCtx.createGain();
        silentGain.gain.value = 0;
        session.processorNode.connect(silentGain);
        silentGain.connect(audioCtx.destination);
        session.silentGain = silentGain;

        // Belt-and-suspenders fallback: if any future tab-suspend / autoplay
        // blip drops the context back to 'suspended', resume on next gesture.
        const unlock = (): void => {
            if (session.audioCtx && session.audioCtx.state === 'suspended') {
                void session.audioCtx.resume();
            }
        };
        window.addEventListener('click', unlock);
        window.addEventListener('keydown', unlock);
        session.unlockHandler = unlock;
    } catch (err) {
        console.error('[useMicStream] Failed to start mic capture:', err);
    } finally {
        session.starting = false;
    }
}

function stopMicSession(): void {
    if (session.unlockHandler) {
        window.removeEventListener('click', session.unlockHandler);
        window.removeEventListener('keydown', session.unlockHandler);
        session.unlockHandler = null;
    }
    try {
        session.processorNode?.disconnect();
        session.sourceNode?.disconnect();
        session.audioCtx?.close();
    } catch {
        // ignore cleanup errors
    }
    session.stream?.getTracks().forEach((t) => t.stop());
    session.processorNode = null;
    session.sourceNode = null;
    session.audioCtx = null;
    session.silentGain = null;
    session.stream = null;
    session.pausedRef = null;
    session.firstFrameLogged = false;
    // starting is reset in the finally block of startMicSession, but be safe.
    session.starting = false;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useMicStream({ paused }: UseMicStreamOptions): UseMicStreamReturn {
    const pausedRef = useRef(paused);

    // Keep pausedRef in sync without restarting the stream.
    useEffect(() => {
        pausedRef.current = paused;
    }, [paused]);

    useEffect(() => {
        session.refCount += 1;

        if (session.refCount === 1) {
            void startMicSession(pausedRef);
        }

        return () => {
            session.refCount -= 1;

            if (session.refCount === 0) {
                // Defer stop slightly so StrictMode's unmount/remount cycle
                // (mount → cleanup → remount in dev) doesn't churn the AudioContext.
                setTimeout(() => {
                    if (session.refCount === 0) {
                        stopMicSession();
                    }
                }, 100);
            }
        };
        // We intentionally run this once — wsClient is a module-level singleton
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // isCapturing is true when the AudioContext is live.
    return { isCapturing: session.audioCtx !== null };
}

// ---------------------------------------------------------------------------
// Helpers (module-scope, not exported — consumed only inside this file)
// ---------------------------------------------------------------------------

/**
 * Convert a Float32Array of audio samples to an Int16Array.
 * If the AudioContext couldn't honour the 16 kHz request, downsample linearly.
 */
function floatToInt16(float32: Float32Array, sourceSampleRate: number): Int16Array {
    const targetSampleRate = 16000;
    let samples: Float32Array;

    if (sourceSampleRate !== targetSampleRate) {
        // Linear downsampling
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
        // Clamp and scale
        const clamped = Math.max(-1, Math.min(1, samples[i]));
        int16[i] = clamped < 0 ? clamped * 32768 : clamped * 32767;
    }
    return int16;
}
