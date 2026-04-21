import { useEffect, useRef, type RefObject } from 'react';
import { createOrb, type Orb } from '../lib/orb';

/**
 * Return value of {@link useOrb}.
 */
export interface UseOrbResult {
  orbRef: RefObject<Orb | null>;
  /**
   * The raw WebGL2 (or WebGL1) rendering context of the orb canvas after
   * the orb engine has initialised.
   *
   * Exposed so that callers can inspect renderer state without modifying
   * `lib/orb.ts`. Calling `gl.clearColor(r,g,b,a)` here has no sustained
   * effect because the Three.js renderer re-applies its own clear colour on
   * every frame. True canvas transparency requires `alpha: true` in the
   * `WebGLRenderer` constructor inside `lib/orb.ts` — that is outside the
   * scope of this hook.
   *
   * The ref is populated after the first canvas mount and is `null` before
   * mount or after destroy.
   */
  glRef: RefObject<WebGL2RenderingContext | WebGLRenderingContext | null>;
}

/**
 * Hook to create and manage the Three.js orb instance.
 *
 * Returns both the orb ref and a ref to the canvas WebGL context so that
 * callers can inspect or post-configure low-level GL state without touching
 * `lib/orb.ts`.
 */
export function useOrb(
  canvasRef: RefObject<HTMLCanvasElement | null>,
): UseOrbResult {
  const orbRef = useRef<Orb | null>(null);
  const glRef = useRef<WebGL2RenderingContext | WebGLRenderingContext | null>(null);

  useEffect(() => {
    if (!canvasRef.current) return;

    // Pass alpha: true so the Scene background (grid, stars) shows through
    // the particle gaps in the classic Three.js orb.
    orbRef.current = createOrb(canvasRef.current, { alpha: true });

    // Capture the GL context that the orb engine bound to the canvas.
    // `getContext` returns the already-created context (not a new one) when
    // called after Three.js has initialised — WebGL contexts are singletons
    // per canvas element.
    glRef.current =
      (canvasRef.current.getContext('webgl2') as WebGL2RenderingContext | null) ??
      (canvasRef.current.getContext('webgl') as WebGLRenderingContext | null);

    return () => {
      if (orbRef.current) {
        orbRef.current.destroy();
        orbRef.current = null;
      }
      glRef.current = null;
    };
  }, [canvasRef]);

  return { orbRef, glRef };
}
