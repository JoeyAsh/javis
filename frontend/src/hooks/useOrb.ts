import { useEffect, useRef, type RefObject } from 'react';
import { createOrb, type Orb } from '../lib/orb';

/**
 * Hook to create and manage the Three.js orb instance.
 */
export function useOrb(
  canvasRef: RefObject<HTMLCanvasElement | null>
): RefObject<Orb | null> {
  const orbRef = useRef<Orb | null>(null);

  useEffect(() => {
    if (!canvasRef.current) return;

    orbRef.current = createOrb(canvasRef.current);

    return () => {
      if (orbRef.current) {
        orbRef.current.destroy();
        orbRef.current = null;
      }
    };
  }, [canvasRef]);

  return orbRef;
}
