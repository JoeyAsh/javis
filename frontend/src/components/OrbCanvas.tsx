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
  /**
   * Live conversation-mode follow-up state. When `active` is true the orb
   * stays in a muted pulse; the last 5 s render a thin countdown ring.
   */
  followUp?: {
    active: boolean;
    secondsRemaining: number;
  };
}

/**
 * Full-screen canvas component displaying the Three.js particle orb.
 */
export function OrbCanvas({
  orbState,
  analyser,
  mockMode = null,
  followUp,
}: OrbCanvasProps) {
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

  useEffect(() => {
    if (followUp) {
      orbRef.current?.setFollowUp(followUp.active, followUp.secondsRemaining);
    } else {
      orbRef.current?.setFollowUp(false, 0);
    }
  }, [followUp, orbRef]);

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 w-screen h-screen"
      style={{ zIndex: 0 }}
    />
  );
}

export default OrbCanvas;
