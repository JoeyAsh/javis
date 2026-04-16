import { useEffect, useRef } from 'react';
import { useOrb } from '../hooks/useOrb';
import type { OrbState } from '../types';

interface OrbCanvasProps {
  orbState: OrbState;
  analyser: AnalyserNode | null;
  /**
   * When set (dev-menu override), the orb synthesises internal amplitude
   * patterns appropriate for that state instead of reading the analyser.
   */
  mockMode?: OrbState | null;
}

/**
 * Full-screen canvas component displaying the Three.js particle orb.
 */
export function OrbCanvas({ orbState, analyser, mockMode = null }: OrbCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const orbRef = useOrb(canvasRef);

  useEffect(() => {
    orbRef.current?.setState(orbState);
  }, [orbState, orbRef]);

  useEffect(() => {
    orbRef.current?.setAnalyser(analyser);
  }, [analyser, orbRef]);

  useEffect(() => {
    orbRef.current?.setMockMode(mockMode);
  }, [mockMode, orbRef]);

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 w-screen h-screen"
      style={{ zIndex: 0 }}
    />
  );
}

export default OrbCanvas;
