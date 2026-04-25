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
 */
export function OrbCanvas({
  orbState,
  analyser,
  mockMode = null,
  followUp,
}: OrbCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const orbRef = useOrb(canvasRef);

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
    <div className="fixed inset-0 w-screen h-screen" style={{ zIndex: 0 }}>
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
