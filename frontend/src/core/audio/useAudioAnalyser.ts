/**
 * useAudioAnalyser — decodes and plays back base64 MP3 audio from the backend.
 * Copy of src/hooks/useAudioAnalyser.ts — original remains in place.
 * No relative import changes needed (was already self-contained).
 */

import { useCallback, useEffect, useRef, useState } from 'react';

interface UseAudioAnalyserReturn {
    analyser: AnalyserNode | null;
    isSpeaking: boolean;
    enqueue: (base64Mp3: string, volume?: number, channel?: string) => void;
    /** Stop the currently playing clip and clear the entire queue. */
    stopAll: () => void;
}

export function useAudioAnalyser(): UseAudioAnalyserReturn {
    const [analyser, setAnalyser] = useState<AnalyserNode | null>(null);
    const [isSpeaking, setIsSpeaking] = useState(false);

    const audioCtxRef = useRef<AudioContext | null>(null);
    const analyserRef = useRef<AnalyserNode | null>(null);
    const queueRef = useRef<Array<{ data: string; volume: number; channel: string }>>([]);
    const playingRef = useRef(false);
    const speechPlayingRef = useRef(false);
    const activeSourceRef = useRef<AudioBufferSourceNode | null>(null);
    const gainRef = useRef<GainNode | null>(null);

    const getAudioContext = useCallback((): AudioContext => {
        if (!audioCtxRef.current || audioCtxRef.current.state === 'closed') {
            const ctx = new AudioContext();
            const node = ctx.createAnalyser();
            node.fftSize = 256;
            node.smoothingTimeConstant = 0.8;
            node.connect(ctx.destination);
            audioCtxRef.current = ctx;
            analyserRef.current = node;
            setAnalyser(node);
        }
        return audioCtxRef.current;
    }, []);

    const playNext = useCallback(async () => {
        if (playingRef.current || queueRef.current.length === 0) return;

        const item = queueRef.current[0];

        if (item.channel === 'notification') {
            const hasSpeechAhead =
                speechPlayingRef.current || queueRef.current.some((q) => q.channel === 'speech');
            if (hasSpeechAhead) return;
        }

        playingRef.current = true;
        speechPlayingRef.current = item.channel === 'speech';
        setIsSpeaking(true);

        try {
            const ctx = getAudioContext();

            if (ctx.state === 'suspended') {
                await ctx.resume();
            }

            const binary = atob(item.data);
            const bytes = new Uint8Array(binary.length);
            for (let i = 0; i < binary.length; i++) {
                bytes[i] = binary.charCodeAt(i);
            }

            const audioBuffer = await ctx.decodeAudioData(bytes.buffer);

            const source = ctx.createBufferSource();
            source.buffer = audioBuffer;

            const gain = ctx.createGain();
            gain.gain.value = item.volume;
            gainRef.current = gain;
            activeSourceRef.current = source;

            source.connect(gain);
            const analyserNode = analyserRef.current;
            if (!analyserNode) {
                activeSourceRef.current = null;
                gainRef.current = null;
                speechPlayingRef.current = false;
                queueRef.current = queueRef.current.slice(1);
                playingRef.current = false;
                if (queueRef.current.length === 0) {
                    setIsSpeaking(false);
                } else {
                    void playNext();
                }
                return;
            }
            gain.connect(analyserNode);

            source.onended = () => {
                activeSourceRef.current = null;
                gainRef.current = null;
                speechPlayingRef.current = false;
                queueRef.current = queueRef.current.slice(1);
                playingRef.current = false;
                if (queueRef.current.length === 0) {
                    setIsSpeaking(false);
                } else {
                    void playNext();
                }
            };

            source.start();
        } catch (err) {
            console.error('[audio] playback error:', err);
            activeSourceRef.current = null;
            gainRef.current = null;
            speechPlayingRef.current = false;
            queueRef.current = queueRef.current.slice(1);
            playingRef.current = false;
            if (queueRef.current.length === 0) {
                setIsSpeaking(false);
            } else {
                void playNext();
            }
        }
    }, [getAudioContext]);

    const enqueue = useCallback(
        (base64Mp3: string, volume = 1.0, channel = 'speech') => {
            queueRef.current = [...queueRef.current, { data: base64Mp3, volume, channel }];
            void playNext();
        },
        [playNext],
    );

    const stopAll = useCallback(() => {
        try {
            activeSourceRef.current?.stop();
        } catch {
            // Already stopped — safe to ignore.
        }
        activeSourceRef.current = null;
        gainRef.current = null;
        speechPlayingRef.current = false;
        queueRef.current = [];
        playingRef.current = false;
        setIsSpeaking(false);
    }, []);

    useEffect(() => {
        return () => {
            stopAll();
            audioCtxRef.current?.close();
            audioCtxRef.current = null;
            analyserRef.current = null;
        };
    }, [stopAll]);

    return { analyser, isSpeaking, enqueue, stopAll };
}

export default useAudioAnalyser;
