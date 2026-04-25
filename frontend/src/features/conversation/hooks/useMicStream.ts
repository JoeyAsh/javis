import { useEffect, useRef } from 'react';
import { wsClient } from '@core/websocket/wsClient';
import type { UseMicStreamOptions, UseMicStreamReturn } from './useMicStream.types';

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
 */
export function useMicStream({ paused }: UseMicStreamOptions): UseMicStreamReturn {
    const isCapturingRef = useRef(false);
    const pausedRef = useRef(paused);

    // Keep pausedRef in sync without restarting the stream
    useEffect(() => {
        pausedRef.current = paused;
    }, [paused]);

    useEffect(() => {
        let audioCtx: AudioContext | null = null;
        let sourceNode: MediaStreamAudioSourceNode | null = null;
        // ScriptProcessorNode is deprecated but has the widest browser support
        // for real-time raw PCM access without an AudioWorklet bundler setup.
        // eslint-disable-next-line @typescript-eslint/no-deprecated
        let processorNode: ScriptProcessorNode | null = null;
        let stream: MediaStream | null = null;
        let destroyed = false;
        let unlockListeners: (() => void) | null = null;
        let firstFrameLogged = false;

        async function start(): Promise<void> {
            try {
                stream = await navigator.mediaDevices.getUserMedia({
                    audio: {
                        channelCount: 1,
                        sampleRate: 16000,
                        echoCancellation: true,
                        noiseSuppression: true,
                        autoGainControl: true,
                    },
                });

                if (destroyed) {
                    stream.getTracks().forEach((t) => t.stop());
                    return;
                }

                // Request 16 kHz explicitly; browser may not honour it — we downsample
                // in the processor if needed.
                audioCtx = new AudioContext({ sampleRate: 16000 });

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

                sourceNode = audioCtx.createMediaStreamSource(stream);

                // bufferSize=4096 gives ~256 ms at 16 kHz — a good balance between
                // latency and CPU. Use mono (1 channel).
                // eslint-disable-next-line @typescript-eslint/no-deprecated
                processorNode = audioCtx.createScriptProcessor(4096, 1, 1);

                processorNode.onaudioprocess = (event: AudioProcessingEvent) => {
                    if (pausedRef.current) return;

                    const inputBuffer = event.inputBuffer;
                    const float32 = inputBuffer.getChannelData(0);

                    // Convert float32 [-1, 1] → int16 [-32768, 32767]
                    const int16 = floatToInt16(float32, inputBuffer.sampleRate);

                    if (!firstFrameLogged) {
                        console.info(
                            `[useMicStream] First PCM frame: ${int16.length} samples, sr=${inputBuffer.sampleRate}, ctxState=${audioCtx?.state}`,
                        );
                        firstFrameLogged = true;
                    }
                    wsClient.sendBinary(int16.buffer as ArrayBuffer);
                };

                sourceNode.connect(processorNode);
                // Connect to destination with zero gain so the browser doesn't echo
                // the mic back to the speakers but still runs the graph.
                const silentGain = audioCtx.createGain();
                silentGain.gain.value = 0;
                processorNode.connect(silentGain);
                silentGain.connect(audioCtx.destination);

                isCapturingRef.current = true;

                // Belt-and-suspenders fallback: if any future tab-suspend / autoplay
                // blip drops the context back to 'suspended', resume on next gesture.
                const unlock = (): void => {
                    if (audioCtx && audioCtx.state === 'suspended') {
                        void audioCtx.resume();
                    }
                };
                window.addEventListener('click', unlock);
                window.addEventListener('keydown', unlock);

                // Stash on the closure so cleanup can remove them.
                unlockListeners = unlock;
            } catch (err) {
                console.error('[useMicStream] Failed to start mic capture:', err);
            }
        }

        function stop(): void {
            if (unlockListeners) {
                window.removeEventListener('click', unlockListeners);
                window.removeEventListener('keydown', unlockListeners);
                unlockListeners = null;
            }
            isCapturingRef.current = false;
            try {
                processorNode?.disconnect();
                sourceNode?.disconnect();
                audioCtx?.close();
            } catch {
                // ignore cleanup errors
            }
            stream?.getTracks().forEach((t) => t.stop());
            processorNode = null;
            sourceNode = null;
            audioCtx = null;
            stream = null;
        }

        void start();

        return () => {
            destroyed = true;
            stop();
        };
        // We intentionally run this once — wsClient is a module-level singleton
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    return { isCapturing: isCapturingRef.current };
}

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
