import { useEffect, useState } from 'react';
import type { CSSProperties, ReactElement } from 'react';
import { computeSnapRect, useWindowManager } from './WindowManager';
import type { SnapRect } from './WindowManager';

/**
 * Renders a glowing rectangle covering the snap target while a drag is
 * hovering a snap zone. Sits above all windows and below the idle mask. The
 * overlay container is always mounted (so CSS transitions are smooth); the
 * highlighted zone rect only renders when `activeSnap !== null`.
 */
export function SnapOverlay(): ReactElement {
  const { activeSnap } = useWindowManager();
  const [viewport, setViewport] = useState<{ w: number; h: number }>(() => ({
    w: typeof window !== 'undefined' ? window.innerWidth : 1920,
    h: typeof window !== 'undefined' ? window.innerHeight : 1080,
  }));

  // Track viewport so the overlay follows live resizes while a drag is active.
  useEffect(() => {
    const onResize = (): void => {
      setViewport({ w: window.innerWidth, h: window.innerHeight });
    };
    window.addEventListener('resize', onResize);
    return () => {
      window.removeEventListener('resize', onResize);
    };
  }, []);

  let rect: SnapRect | null = null;
  if (activeSnap !== null) {
    rect = computeSnapRect(activeSnap, viewport.w, viewport.h);
  }

  const style: CSSProperties | undefined = rect
    ? {
        left: rect.x,
        top: rect.y,
        width: rect.w,
        height: rect.h,
      }
    : undefined;

  return (
    <div className="snap-overlay" aria-hidden>
      {rect !== null && style !== undefined && (
        <div
          key={activeSnap ?? 'none'}
          className="snap-zone"
          style={style}
        />
      )}
    </div>
  );
}

export default SnapOverlay;
