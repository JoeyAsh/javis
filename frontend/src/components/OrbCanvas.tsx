import { useEffect, useRef } from 'react';
import { useOrb } from '../hooks/useOrb';
import type { AppOrbState, OrbState } from '../types';

interface OrbCanvasProps {
  orbState: AppOrbState;
  analyser: AnalyserNode | null;
  /**
   * When set (dev-menu override), the orb synthesises internal amplitude
   * patterns appropriate for that state instead of reading the analyser.
   */
  mockMode?: AppOrbState | null;
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
 * Map from `AppOrbState` to the engine state passed to `orb.setState()`.
 *
 * The Three.js orb engine does not have a `working` preset, so `working` is
 * aliased to `thinking` (tight dense core + fast spin). The amber tint that
 * distinguishes `working` from `thinking` is applied via a CSS mix-blend
 * overlay on top of the canvas — no engine modifications needed.
 */
function toEngineState(s: AppOrbState): OrbState {
  if (s === 'working') return 'thinking';
  return s;
}

/**
 * Full-screen canvas component displaying the Three.js particle orb.
 *
 * When `orbState === 'working'`, the engine runs the `thinking` preset and
 * a translucent amber overlay (`--orb-working`) is composited on top via
 * `mix-blend-mode: color` so the particle cloud picks up a warm tint that
 * visually distinguishes tool execution from pure cognitive thinking (blue).
 *
 * ## Canvas transparency
 *
 * The Three.js WebGL context inside `lib/orb.ts` is created without
 * `alpha: true`, which means the canvas backing store is opaque regardless
 * of what clear colour is set. The `glRef` exposed by `useOrb` is captured
 * here for future use once `lib/orb.ts` is updated to pass `alpha: true` to
 * `WebGLRenderer`. At that point, calling `gl.clearColor(0, 0, 0, 0)` after
 * engine init will make the inter-particle space fully transparent so the
 * Scene background shows through.
 */
export function OrbCanvas({
  orbState,
  analyser,
  mockMode = null,
  followUp,
}: OrbCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const { orbRef, glRef } = useOrb(canvasRef);

  // Post-init: attempt to configure the clear colour to transparent so the
  // Hypermodern Scene background is visible between particles.
  // NOTE: This has no visual effect while `lib/orb.ts` creates the WebGL
  // context with `alpha: false` (the current default). The Three.js renderer
  // re-applies its own clear colour (0x050508 @ 1.0) on every frame, so the
  // `gl.clearColor` call below is overridden immediately. True transparency
  // requires updating the `WebGLRenderer` constructor call in `lib/orb.ts`
  // to pass `{ alpha: true, premultipliedAlpha: false }`. This effect is
  // intentionally left in place so that it activates automatically once that
  // upstream change lands — without requiring another touch to OrbCanvas.
  useEffect(() => {
    const gl = glRef.current;
    if (!gl) return;
    gl.clearColor(0, 0, 0, 0);
  }, [glRef]);

  useEffect(() => {
    orbRef.current?.setState(toEngineState(orbState));
  }, [orbState, orbRef]);

  useEffect(() => {
    orbRef.current?.setAnalyser(analyser);
  }, [analyser, orbRef]);

  useEffect(() => {
    // When mockMode is `working`, pass `thinking` to the engine mock path too.
    orbRef.current?.setMockMode(mockMode !== null ? toEngineState(mockMode) : null);
  }, [mockMode, orbRef]);

  useEffect(() => {
    if (followUp) {
      orbRef.current?.setFollowUp(followUp.active, followUp.secondsRemaining);
    } else {
      orbRef.current?.setFollowUp(false, 0);
    }
  }, [followUp, orbRef]);

  const isWorking = orbState === 'working';

  return (
    <div className="fixed inset-0 w-screen h-screen" style={{ zIndex: 1 }}>
      <canvas ref={canvasRef} className="absolute inset-0 w-full h-full" />
      {/* Amber tint overlay — visible only in `working` state. Uses
          mix-blend-mode: color to tint the canvas particles without
          flattening the additive particle bloom. Opacity fades over 400 ms. */}
      <div
        aria-hidden="true"
        style={{
          position: 'absolute',
          inset: 0,
          background: 'var(--orb-working)',
          mixBlendMode: 'color',
          opacity: isWorking ? 1 : 0,
          transition: 'opacity 400ms ease',
          pointerEvents: 'none',
        }}
      />
    </div>
  );
}

export default OrbCanvas;
