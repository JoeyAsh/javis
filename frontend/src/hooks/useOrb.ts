import { useEffect, useRef, type RefObject } from 'react';
import { Orb } from '../lib/orb';

/**
 * Hook to create and manage the Three.js orb instance.
 */
export function useOrb(
  canvasRef: RefObject<HTMLCanvasElement>
): RefObject<Orb | null> {
  const orbRef = useRef<Orb | null>(null);

  useEffect(() => {
    if (!canvasRef.current) return;

    // Create orb instance
    orbRef.current = new Orb(canvasRef.current);

    // Cleanup on unmount
    return () => {
      if (orbRef.current) {
        orbRef.current.destroy();
        orbRef.current = null;
      }
    };
  }, [canvasRef]);

  return orbRef;
}
