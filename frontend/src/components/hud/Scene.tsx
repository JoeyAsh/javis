/**
 * Scene — layered fixed full-screen background for the JARVIS HUD.
 *
 * Layers (bottom to top, all `pointer-events: none`):
 *   1. Radial background gradient (deepens centre)
 *   2. Optional 44×44 px cyan grid with `gridDrift` 28 s animation
 *   3. Optional scanlines (mix-blend-mode: screen)
 *   4. SVG turbulence noise overlay (data-URI)
 *   5. Horizon glow strip at 60 % from top
 *   6. Optional stars (60 random dots with individual twinkle delays)
 *   7. Vignette (radial dark edge)
 *   8. Reactor radial-gradient (900×900 px centred glow)
 *
 * `prefers-reduced-motion` pauses ALL animations.
 * `will-change: transform` is applied to animated layers only.
 */

import { useMemo } from 'react';
import type { CSSProperties, ReactElement } from 'react';

export interface SceneProps {
  /** Show the animated grid underlay. */
  grid?: boolean;
  /** Show the repeating scanline overlay. */
  scan?: boolean;
  /** Show 60 random twinkling stars. */
  stars?: boolean;
}

// ---------------------------------------------------------------------------
// Keyframes injected once as a <style> block.
// ---------------------------------------------------------------------------

const SCENE_STYLE = `
@keyframes gridDrift {
  0%   { background-position: 0 0; }
  100% { background-position: 44px 44px; }
}

@keyframes starTwinkle {
  0%, 100% { opacity: var(--star-base, 0.4); transform: scale(1); }
  50%       { opacity: var(--star-peak, 0.9); transform: scale(1.4); }
}

@media (prefers-reduced-motion: reduce) {
  .scene-grid     { animation: none !important; }
  .scene-star     { animation: none !important; }
}
`;

// ---------------------------------------------------------------------------
// Star data — stable across renders via useMemo with fixed seed.
// ---------------------------------------------------------------------------

interface StarDatum {
  id: number;
  top: string;
  left: string;
  size: number;
  baseOpacity: number;
  peakOpacity: number;
  duration: number;
  delay: number;
}

function generateStars(count: number): StarDatum[] {
  // Deterministic pseudo-random using a simple LCG seeded to a fixed value
  // so hydration is stable and there's no layout shift between renders.
  let seed = 0x6d2b4a1e;
  const rand = (): number => {
    seed = (seed * 1664525 + 1013904223) & 0xffffffff;
    return (seed >>> 0) / 0xffffffff;
  };

  const stars: StarDatum[] = [];
  for (let i = 0; i < count; i++) {
    stars.push({
      id: i,
      top: `${(rand() * 90).toFixed(2)}%`,
      left: `${(rand() * 100).toFixed(2)}%`,
      size: 1 + rand() * 1.5,
      baseOpacity: 0.15 + rand() * 0.3,
      peakOpacity: 0.5 + rand() * 0.5,
      duration: 2.5 + rand() * 4,
      delay: -(rand() * 8),
    });
  }
  return stars;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/** Full-screen animated scene background. Mount once at `z-index: 0`. */
export function Scene({ grid = true, scan = true, stars = true }: SceneProps): ReactElement {
  const starData = useMemo(() => generateStars(60), []);

  const rootStyle: CSSProperties = {
    position: 'fixed',
    inset: 0,
    zIndex: 0,
    pointerEvents: 'none',
    overflow: 'hidden',
  };

  // 1. Radial background
  const radialBgStyle: CSSProperties = {
    position: 'absolute',
    inset: 0,
    background:
      'radial-gradient(ellipse 120% 80% at 50% 40%, rgba(13,13,24,0.0) 0%, rgba(5,5,8,0.85) 70%, rgba(5,5,8,1) 100%)',
  };

  // 2. Grid
  const gridStyle: CSSProperties = {
    position: 'absolute',
    inset: 0,
    backgroundImage: [
      'linear-gradient(rgba(76,168,232,0.045) 1px, transparent 1px)',
      'linear-gradient(90deg, rgba(76,168,232,0.045) 1px, transparent 1px)',
    ].join(', '),
    backgroundSize: '44px 44px',
    animation: 'gridDrift 28s linear infinite',
    willChange: 'background-position',
  };

  // 3. Scanlines
  const scanlinesStyle: CSSProperties = {
    position: 'absolute',
    inset: 0,
    background:
      'repeating-linear-gradient(to bottom, transparent 0, transparent 2px, rgba(76,168,232,0.028) 2px, rgba(76,168,232,0.028) 3px)',
    mixBlendMode: 'screen',
  };

  // 4. SVG turbulence noise (data-URI, inline base64 — small enough to inline)
  // A minimal 100×100 SVG with a feTurbulence filter for organic grain texture.
  const noiseSvg = `<svg xmlns='http://www.w3.org/2000/svg' width='200' height='200'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.75' numOctaves='4' stitchTiles='stitch'/><feColorMatrix type='saturate' values='0'/></filter><rect width='200' height='200' filter='url(%23n)' opacity='0.04'/></svg>`;
  const noiseStyle: CSSProperties = {
    position: 'absolute',
    inset: 0,
    backgroundImage: `url("data:image/svg+xml,${noiseSvg}")`,
    backgroundSize: '200px 200px',
    opacity: 0.6,
    mixBlendMode: 'overlay',
  };

  // 5. Horizon glow — horizontal strip at ~60 % from top.
  const horizonStyle: CSSProperties = {
    position: 'absolute',
    left: 0,
    right: 0,
    top: '60%',
    height: 1,
    background:
      'linear-gradient(90deg, transparent 0%, rgba(76,168,232,0.18) 20%, rgba(76,168,232,0.35) 50%, rgba(76,168,232,0.18) 80%, transparent 100%)',
    boxShadow: '0 0 20px 4px rgba(76,168,232,0.12)',
  };

  // 7. Vignette
  const vignetteStyle: CSSProperties = {
    position: 'absolute',
    inset: 0,
    background:
      'radial-gradient(ellipse 100% 100% at 50% 50%, transparent 40%, rgba(5,5,8,0.65) 100%)',
  };

  // 8. Reactor glow (900×900 px centred)
  const reactorStyle: CSSProperties = {
    position: 'absolute',
    top: '50%',
    left: '50%',
    transform: 'translate(-50%, -50%)',
    width: 900,
    height: 900,
    background:
      'radial-gradient(ellipse at 50% 50%, rgba(76,168,232,0.06) 0%, rgba(76,168,232,0.02) 35%, transparent 70%)',
    borderRadius: '50%',
  };

  return (
    <>
      {/* Inject keyframes once */}
      <style dangerouslySetInnerHTML={{ __html: SCENE_STYLE }} />

      <div style={rootStyle} aria-hidden>
        {/* 1. Radial bg */}
        <div style={radialBgStyle} />

        {/* 2. Grid */}
        {grid && <div className="scene-grid" style={gridStyle} />}

        {/* 3. Scanlines */}
        {scan && <div style={scanlinesStyle} />}

        {/* 4. Noise */}
        <div style={noiseStyle} />

        {/* 5. Horizon glow */}
        <div style={horizonStyle} />

        {/* 6. Stars */}
        {stars &&
          starData.map((s) => {
            const starStyle: CSSProperties = {
              position: 'absolute',
              top: s.top,
              left: s.left,
              width: s.size,
              height: s.size,
              borderRadius: '50%',
              background: 'rgba(232,244,255,1)',
              // CSS custom properties for the twinkle keyframe opacity values.
              ['--star-base' as string]: s.baseOpacity,
              ['--star-peak' as string]: s.peakOpacity,
              opacity: s.baseOpacity,
              animation: `starTwinkle ${s.duration.toFixed(2)}s ease-in-out ${s.delay.toFixed(2)}s infinite`,
              willChange: 'opacity, transform',
            };
            return <span key={s.id} className="scene-star" style={starStyle} />;
          })}

        {/* 7. Vignette */}
        <div style={vignetteStyle} />

        {/* 8. Reactor glow */}
        <div style={reactorStyle} />
      </div>
    </>
  );
}

export default Scene;
