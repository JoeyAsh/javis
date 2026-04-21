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

// Particle configuration — 6 orbiters matching prototype exactly.
// { r: radius px, dur: period seconds, size: px, col: CSS var, dir: +1|-1 }
interface ParticleConfig {
  r: number;
  dur: number;
  size: number;
  col: string;
  dir: 1 | -1;
}

const PARTICLES: readonly ParticleConfig[] = [
  { r: 180, dur: 10, size: 3, col: '--accent-bright', dir:  1 },
  { r: 210, dur: 14, size: 2, col: '--accent',        dir: -1 },
  { r: 240, dur: 16, size: 2, col: '--accent-bright', dir:  1 },
  { r: 265, dur: 20, size: 3, col: '--accent',        dir: -1 },
  { r: 295, dur: 24, size: 2, col: '--accent-speak',  dir:  1 },
  { r: 330, dur: 28, size: 3, col: '--accent-bright', dir: -1 },
] as const;

interface ParticlePos {
  x: number;
  y: number;
}

function computeParticle(p: ParticleConfig, tSec: number, idx: number): ParticlePos {
  const ang = (tSec * (2 * Math.PI) / p.dur) * p.dir + idx * 1.05;
  return {
    x: Math.cos(ang) * p.r,
    y: Math.sin(ang) * p.r,
  };
}

/**
 * Hypermodern CSS orb. Renders 5 rotating rings, 36-tick tick-ring on r2,
 * 3 pulse rings for listening state, and 6 RAF-driven orbiting particles.
 */
export function Orb({ state, rings = true, particles = true }: OrbProps): ReactElement {
  const [particlePositions, setParticlePositions] = useState<ParticlePos[]>(
    () => PARTICLES.map((p, i) => computeParticle(p, 0, i)),
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
      const tSec = (ts - startTimeRef.current) / 1000;

      setParticlePositions(PARTICLES.map((p, i) => computeParticle(p, tSec, i)));

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
          {/* r2 actual ring */}
          <div className="ring r2" />
          {/* Tick ring — 36 ticks × 10°, 460 px radius, 110 s */}
          <div className="ring-ticks">
            {Array.from({ length: 36 }).map((_, i) => (
              <i
                key={i}
                style={{ transform: `translateX(-50%) rotate(${i * 10}deg)` }}
              />
            ))}
          </div>
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

      {/* Orbiting particles — 6 particles, position driven by RAF */}
      {particles &&
        particlePositions.map((pos, i) => {
          const p = PARTICLES[i];
          return (
            <span
              key={i}
              className="particle"
              style={{
                width: p.size,
                height: p.size,
                background: `var(${p.col})`,
                boxShadow: `0 0 ${p.size * 3}px var(${p.col})`,
                transform: `translate(${pos.x}px, ${pos.y}px)`,
              }}
            />
          );
        })}
    </div>
  );
}

export default Orb;
