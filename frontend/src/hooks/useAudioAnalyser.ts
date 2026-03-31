import { useEffect, useState } from 'react';

/**
 * Hook to create an AudioContext and AnalyserNode from microphone input.
 */
export function useAudioAnalyser(): AnalyserNode | null {
  const [analyser, setAnalyser] = useState<AnalyserNode | null>(null);

  useEffect(() => {
    let audioContext: AudioContext | null = null;
    let stream: MediaStream | null = null;

    async function setupAudio() {
      try {
        // Request microphone access
        stream = await navigator.mediaDevices.getUserMedia({ audio: true });

        // Create audio context
        audioContext = new AudioContext();

        // Create analyser node
        const analyserNode = audioContext.createAnalyser();
        analyserNode.fftSize = 256;
        analyserNode.smoothingTimeConstant = 0.8;

        // Connect microphone to analyser
        const source = audioContext.createMediaStreamSource(stream);
        source.connect(analyserNode);

        setAnalyser(analyserNode);
      } catch (error) {
        console.warn('Could not access microphone for audio visualization:', error);
        setAnalyser(null);
      }
    }

    setupAudio();

    // Cleanup
    return () => {
      if (stream) {
        stream.getTracks().forEach((track) => track.stop());
      }
      if (audioContext) {
        audioContext.close();
      }
      setAnalyser(null);
    };
  }, []);

  return analyser;
}
