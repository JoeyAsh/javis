/**
 * ThreeOrb — React wrapper around the Three.js particle orb (lib/orb.ts).
 *
 * Renders a fullscreen canvas and drives the orb via its public API.
 * Does NOT modify lib/orb.ts — only interacts via createOrb().
 */
import { useEffect, useRef, type ReactElement } from 'react';
import { createOrb } from '../lib/orb';
import type { Orb } from '../lib/orb';
import type { OrbState as LibOrbState } from '../lib/primitives/Orb/Orb';
import type { OrbState as TypesOrbState } from '../types';

export interface ThreeOrbProps {
    state: LibOrbState;
    className?: string;
}

export function ThreeOrb({ state, className }: ThreeOrbProps): ReactElement {
    const canvasRef = useRef<HTMLCanvasElement | null>(null);
    const orbRef = useRef<Orb | null>(null);

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;

        const orb = createOrb(canvas, { alpha: true });
        orbRef.current = orb;

        return () => {
            orb.destroy();
            orbRef.current = null;
        };
    }, []);

    useEffect(() => {
        // lib/orb.ts uses types.OrbState which doesn't include 'working'
        // — map 'working' → 'thinking' for the Three.js orb.
        const mapped: TypesOrbState = state === 'working' ? 'thinking' : state;
        orbRef.current?.setState(mapped);
    }, [state]);

    return (
        <canvas
            ref={canvasRef}
            className={className}
            style={{
                position: 'fixed',
                top: 0,
                left: 0,
                pointerEvents: 'none',
                zIndex: 0,
            }}
        />
    );
}

export default ThreeOrb;





