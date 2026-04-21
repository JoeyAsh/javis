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
import './hud.css';
import './Scene.css';

// ---------------------------------------------------------------------------
// Keyframes injected once as a <style> block.
// Scene.css imports the keyframes from hud.css for the production build.
// The <style> block is retained so RTL tests (JSDOM) can assert on keyframe
// presence — JSDOM does not process imported CSS files.
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
  .hud-scene__layer--grid { animation: none !important; }
  .scene-star             { animation: none !important; }
}
`;

export interface SceneProps {
  /** Show the animated grid underlay. */
  grid?: boolean;
  /** Show the repeating scanline overlay. */
  scan?: boolean;
  /** Show 60 random twinkling stars. */
  stars?: boolean;
}

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

// Minimal SVG turbulence noise for organic grain texture (data-URI, static).
const NOISE_SVG = `<svg xmlns='http://www.w3.org/2000/svg' width='200' height='200'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.75' numOctaves='4' stitchTiles='stitch'/><feColorMatrix type='saturate' values='0'/></filter><rect width='200' height='200' filter='url(%23n)' opacity='0.04'/></svg>`;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/** Full-screen animated scene background. Mount once at `z-index: 0`. */
export function Scene({ grid = true, scan = true, stars = true }: SceneProps): ReactElement {
  const starData = useMemo(() => generateStars(60), []);

  return (
    <>
      {/* Inject keyframes once — retained for JSDOM test assertions */}
      <style dangerouslySetInnerHTML={{ __html: SCENE_STYLE }} />

      <div className="hud-scene" aria-hidden>
      {/* 1. Radial bg */}
      <div className="hud-scene__layer hud-scene__layer--radial-bg" />

      {/* 2. Grid */}
      {grid && <div className="hud-scene__layer hud-scene__layer--grid scene-grid" />}

      {/* 3. Scanlines */}
      {scan && <div className="hud-scene__layer hud-scene__layer--scanlines" />}

      {/* 4. Noise — background-image set inline because it contains a data-URI */}
      <div
        className="hud-scene__layer hud-scene__layer--noise"
        style={{ backgroundImage: `url("data:image/svg+xml,${NOISE_SVG}")` }}
      />

      {/* 5. Horizon glow */}
      <div className="hud-scene__layer hud-scene__layer--horizon" />

      {/* 6. Stars — position/size/timing are dynamic per star datum */}
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
      <div className="hud-scene__layer hud-scene__layer--vignette" />

      {/* 8. Reactor glow — per spec: centred at bottom-of-screen minus 90px.
           900px tall, so top places the centre 360px below the viewport. */}
      <div
        className="hud-scene__layer--reactor"
        style={{
          position: 'absolute',
          top: 'calc(100vh - 90px)',
          left: '50%',
          transform: 'translate(-50%, 0)',
          width: 900,
          height: 900,
        }}
      />
    </div>
    </>
  );
}

export default Scene;
