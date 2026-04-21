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
 *
 * Note: Reactor halo is a separate <Reactor /> component mounted in App.tsx.
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
@keyframes gridDrift { to { background-position: 44px 44px, 44px 44px; } }

@keyframes twinkle { 0%,100%{opacity:.2} 50%{opacity:1} }

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
// Matches prototype: 60 stars, position + delay deterministic.
// ---------------------------------------------------------------------------

interface StarDatum {
    id: number;
    top: string;
    left: string;
    delay: string;
}

function generateStars(count: number): StarDatum[] {
    // Deterministic LCG so star positions never shift between renders.
    let seed = 0x6d2b4a1e;
    const rand = (): number => {
        seed = (seed * 1664525 + 1013904223) & 0xffffffff;
        return (seed >>> 0) / 0xffffffff;
    };

    const stars: StarDatum[] = [];
    for (let i = 0; i < count; i++) {
        stars.push({
            id: i,
            left: `${(rand() * 100).toFixed(2)}%`,
            top: `${(rand() * 100).toFixed(2)}%`,
            delay: `${(rand() * 4).toFixed(2)}s`,
        });
    }
    return stars;
}

// Minimal SVG turbulence noise — baseFrequency 0.9 matches prototype.
const NOISE_SVG = `<svg xmlns='http://www.w3.org/2000/svg' width='200' height='200'><filter id='n'><feTurbulence baseFrequency='0.9' stitchTiles='stitch'/></filter><rect width='100%' height='100%' filter='url(%23n)' opacity='0.55'/></svg>`;

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
                {/* Grid — 44×44 px drifting, ellipse-masked */}
                {grid && <div className="hud-scene__layer hud-scene__layer--grid" />}

                {/* Scanlines — 3px/1px repeating, screen blend */}
                {scan && <div className="hud-scene__layer hud-scene__layer--scanlines" />}

                {/* Noise — SVG turbulence overlay blend */}
                <div
                    className="hud-scene__layer hud-scene__layer--noise"
                    style={{ backgroundImage: `url("data:image/svg+xml,${NOISE_SVG}")` }}
                />

                {/* Horizon glow — bottom 38% */}
                <div className="hud-scene__layer hud-scene__layer--horizon" />

                {/* Stars — 60 deterministic twinkle dots */}
                <div className="hud-scene__layer hud-scene__layer--stars">
                    {stars &&
                        starData.map((s) => {
                            const starStyle: CSSProperties = {
                                position: 'absolute',
                                left: s.left,
                                top: s.top,
                                width: 1,
                                height: 1,
                                background: 'var(--text)',
                                borderRadius: '50%',
                                boxShadow: '0 0 4px var(--accent-bright)',
                                animation: `twinkle 4s ease-in-out ${s.delay} infinite`,
                            };
                            return <i key={s.id} className="scene-star" style={starStyle} />;
                        })}
                </div>

                {/* Vignette */}
                <div className="hud-scene__layer hud-scene__layer--vignette" />
            </div>
        </>
    );
}

export default Scene;
