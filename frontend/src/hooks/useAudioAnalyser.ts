import { useCallback, useEffect, useRef, useState } from 'react';

interface UseAudioAnalyserReturn {
  analyser: AnalyserNode | null;
  isSpeaking: boolean;
  enqueue: (base64Mp3: string) => void;
}

/**
 * Hook for decoding and playing back base64 MP3 audio from the backend.
 * Creates an AnalyserNode connected to playback for orb visualization.
 * Manages a queue so clips play sequentially.
 */
export function useAudioAnalyser(): UseAudioAnalyserReturn {
  const [analyser, setAnalyser] = useState<AnalyserNode | null>(null);
  const [isSpeaking, setIsSpeaking] = useState(false);

  const audioCtxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const queueRef = useRef<string[]>([]);
  const playingRef = useRef(false);

  // Lazily initialize AudioContext (must be after user gesture in some browsers)
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

    const base64 = queueRef.current[0];
    playingRef.current = true;
    setIsSpeaking(true);

    try {
      const ctx = getAudioContext();

      // Resume context if suspended (autoplay policy)
      if (ctx.state === 'suspended') {
        await ctx.resume();
      }

      // Decode base64 → ArrayBuffer
      const binary = atob(base64);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) {
        bytes[i] = binary.charCodeAt(i);
      }

      const audioBuffer = await ctx.decodeAudioData(bytes.buffer);

      const source = ctx.createBufferSource();
      source.buffer = audioBuffer;
      // Connect source → analyser (analyser already connected to destination)
      source.connect(analyserRef.current!);

      source.onended = () => {
        queueRef.current = queueRef.current.slice(1);
        playingRef.current = false;
        if (queueRef.current.length === 0) {
          setIsSpeaking(false);
        } else {
          playNext();
        }
      };

      source.start();
    } catch (err) {
      console.error('[audio] playback error:', err);
      queueRef.current = queueRef.current.slice(1);
      playingRef.current = false;
      if (queueRef.current.length === 0) {
        setIsSpeaking(false);
      } else {
        playNext();
      }
    }
  }, [getAudioContext]);

  const enqueue = useCallback(
    (base64Mp3: string) => {
      queueRef.current = [...queueRef.current, base64Mp3];
      playNext();
    },
    [playNext]
  );

  useEffect(() => {
    return () => {
      audioCtxRef.current?.close();
      audioCtxRef.current = null;
      analyserRef.current = null;
    };
  }, []);

  return { analyser, isSpeaking, enqueue };
}
