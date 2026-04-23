/**
 * ThreeOrb — React wrapper around the Three.js particle orb (ui/orb/orbEngine.ts).
 *
 * Renders a fullscreen canvas and drives the orb via its public API.
 * Does NOT modify orbEngine.ts — only interacts via createOrb().
 */
import { useEffect, useRef, type ReactElement } from 'react';
import { createOrb } from '../orbEngine';
import type { Orb } from '../orbEngine';
import type { OrbState } from '@common/types';
import type { ThreeOrbProps } from './ThreeOrb.types';

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
        // AppOrbState includes 'working' which orbEngine doesn't handle —
        // map 'working' → 'thinking' for the Three.js orb.
        const mapped: OrbState = state === 'working' ? 'thinking' : state;
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
