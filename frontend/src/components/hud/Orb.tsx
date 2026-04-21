/**
 * Orb — Hypermodern CSS-based orb component for JARVIS.
 *
 * Replaces / augments the Three.js OrbCanvas with a pure CSS / requestAnimationFrame
 * implementation. Swappable via useSettings().orbVariant.
 *
 * States: idle | listening | thinking | speaking | working
 * - idle      → float animation, accent color
 * - listening → slow scale pulse (orbListen), pulse rings, mic-open colour
 * - thinking  → hue-rotate spin (orbThink)
 * - speaking  → box-shadow pulse (orbSpeak)
 * - working   → amber tint via .is-working class
 *
 * Rings: 5 concentric rings at 360/460/580/740/920 px diameter, alternating spin.
 * Tick ring: 36 ticks × 10° on the 460 px ring.
 * Pulse rings: 3 expanding rings (listening state).
 * Particles: 6 orbiting at increasing radii, driven by requestAnimationFrame.
 *
 * Respects prefers-reduced-motion: all animations paused.
 */

import { useEffect, useRef, useState } from 'react';
import type { ReactElement } from 'react';
import './orb.css';

export type HypermodernOrbState = 'idle' | 'listening' | 'thinking' | 'speaking' | 'working';

export interface OrbProps {
  state: HypermodernOrbState;
  rings?: boolean;
  particles?: boolean;
}

// Particle configuration — 6 orbiters at increasing radii.
const PARTICLE_RADII = [180, 210, 240, 265, 295, 330] as const;
const PARTICLE_SPEEDS = [0.0008, 0.0006, 0.0010, 0.0007, 0.0005, 0.0009] as const;
const PARTICLE_OFFSETS = [0, 1.05, 2.09, 3.14, 4.19, 5.24] as const; // ~60° steps

interface ParticlePos {
  x: number;
  y: number;
}

function computeParticle(radius: number, speed: number, offset: number, t: number): ParticlePos {
  const angle = t * speed + offset;
  return {
    x: Math.cos(angle) * radius,
    y: Math.sin(angle) * radius,
  };
}

/**
 * Hypermodern CSS orb. Renders 5 rotating rings, 36-tick tick-ring on r2,
 * 3 pulse rings for listening state, and 6 RAF-driven orbiting particles.
 */
export function Orb({ state, rings = true, particles = true }: OrbProps): ReactElement {
  const [particlePositions, setParticlePositions] = useState<ParticlePos[]>(
    () =>
      PARTICLE_RADII.map((r, i) =>
        computeParticle(r, PARTICLE_SPEEDS[i], PARTICLE_OFFSETS[i], 0),
      ),
  );

  const rafRef = useRef<number | null>(null);
  const startTimeRef = useRef<number | null>(null);

  const reducedMotion =
    typeof window !== 'undefined'
      ? window.matchMedia('(prefers-reduced-motion: reduce)').matches
      : false;

  useEffect(() => {
    if (!particles || reducedMotion) return;

    function tick(ts: number): void {
      if (startTimeRef.current === null) startTimeRef.current = ts;
      const elapsed = ts - startTimeRef.current;

      setParticlePositions(
        PARTICLE_RADII.map((r, i) =>
          computeParticle(r, PARTICLE_SPEEDS[i], PARTICLE_OFFSETS[i], elapsed),
        ),
      );

      rafRef.current = requestAnimationFrame(tick);
    }

    rafRef.current = requestAnimationFrame(tick);

    return () => {
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
    };
  }, [particles, reducedMotion]);

  const rootClass = [
    'orb-wrap',
    `orb-state-${state}`,
    state === 'working' ? 'is-working' : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div className={rootClass} aria-hidden>
      {rings && (
        <>
          {/* r5 — outermost, 920 px */}
          <div className="ring r5" />
          {/* r4 — 740 px */}
          <div className="ring r4" />
          {/* r3 — 580 px */}
          <div className="ring r3" />
          {/* r2 — 460 px — tick ring layer */}
          <div className="ring-ticks">
            {Array.from({ length: 36 }).map((_, i) => (
              <i
                key={i}
                style={{ transform: `rotate(${i * 10}deg) translateY(-230px)` }}
              />
            ))}
          </div>
          {/* r2 actual ring */}
          <div className="ring r2" />
          {/* r1 — innermost, 360 px */}
          <div className="ring r1" />
        </>
      )}

      {/* Core orb */}
      <div className={`orb state-${state}`} />

      {/* Listening pulse rings */}
      <div className="pulse d1" />
      <div className="pulse d2" />
      <div className="pulse d3" />

      {/* Orbiting particles */}
      {particles &&
        particlePositions.map((p, i) => (
          <div
            key={i}
            className="particle"
            style={{ transform: `translate(${p.x}px, ${p.y}px)` }}
          />
        ))}
    </div>
  );
}

export default Orb;
