import { useEffect, useRef } from 'react';
import { useOrb } from '../hooks/useOrb';
import { useAudioAnalyser } from '../hooks/useAudioAnalyser';
import type { OrbState } from '../types';

interface OrbCanvasProps {
  orbState: OrbState;
}

/**
 * Full-screen canvas component displaying the Three.js particle orb.
 */
export function OrbCanvas({ orbState }: OrbCanvasProps) {
  // Explicit null in generic so type satisfies RefObject<HTMLCanvasElement | null>
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const orbRef = useOrb(canvasRef);
  const analyser = useAudioAnalyser();

  // Update orb state when it changes
  useEffect(() => {
    if (orbRef.current) {
      orbRef.current.setState(orbState);
    }
  }, [orbState, orbRef]);

  // Pass analyser to orb for speaking animation
  useEffect(() => {
    if (orbRef.current) {
      orbRef.current.setAnalyser(analyser);
    }
  }, [analyser, orbRef]);

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 w-screen h-screen"
      style={{ zIndex: 0 }}
    />
  );
}

export default OrbCanvas;
