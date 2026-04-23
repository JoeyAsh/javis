/**
 * useMicStream — captures raw microphone audio and streams PCM frames.
 * Copy of src/hooks/useMicStream.ts — original remains in place.
 * No relative import changes needed (was already self-contained).
 */

import { useEffect, useRef } from 'react';
import type React from 'react';

interface UseMicStreamOptions {
    /** Ref to the active WebSocket connection */
    wsRef: React.RefObject<WebSocket | null>;
    /** When true, stop sending audio (e.g. while JARVIS is speaking) */
    paused: boolean;
}

interface UseMicStreamReturn {
    isCapturing: boolean;
}

export function useMicStream({ wsRef, paused }: UseMicStreamOptions): UseMicStreamReturn {
    const isCapturingRef = useRef(false);
    const pausedRef = useRef(paused);
    const cleanupRef = useRef<(() => void) | null>(null);

    useEffect(() => {
        pausedRef.current = paused;
    }, [paused]);

    useEffect(() => {
        let audioCtx: AudioContext | null = null;
        let sourceNode: MediaStreamAudioSourceNode | null = null;
        // eslint-disable-next-line @typescript-eslint/no-deprecated
        let processorNode: ScriptProcessorNode | null = null;
        let stream: MediaStream | null = null;
        let destroyed = false;

        async function start() {
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

                audioCtx = new AudioContext({ sampleRate: 16000 });
                sourceNode = audioCtx.createMediaStreamSource(stream);

                // eslint-disable-next-line @typescript-eslint/no-deprecated
                processorNode = audioCtx.createScriptProcessor(4096, 1, 1);

                processorNode.onaudioprocess = (event: AudioProcessingEvent) => {
                    if (
                        pausedRef.current ||
                        !wsRef.current ||
                        wsRef.current.readyState !== WebSocket.OPEN
                    ) {
                        return;
                    }

                    const inputBuffer = event.inputBuffer;
                    const float32 = inputBuffer.getChannelData(0);
                    const int16 = floatToInt16(float32, inputBuffer.sampleRate);
                    wsRef.current.send(int16.buffer as ArrayBuffer);
                };

                sourceNode.connect(processorNode);
                const silentGain = audioCtx.createGain();
                silentGain.gain.value = 0;
                processorNode.connect(silentGain);
                silentGain.connect(audioCtx.destination);

                isCapturingRef.current = true;
            } catch (err) {
                console.error('[useMicStream] Failed to start mic capture:', err);
            }
        }

        function stop() {
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

        cleanupRef.current = stop;
        start();

        return () => {
            destroyed = true;
            stop();
            cleanupRef.current = null;
        };
        // We intentionally run this once — wsRef is a stable ref object
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    return { isCapturing: isCapturingRef.current };
}

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

export default useMicStream;
