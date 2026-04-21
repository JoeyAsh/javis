/**
 * HudViewportCorners — 4 fixed L-bracket overlays at the corners of the
 * browser viewport. These frame the entire HUD, not individual panels.
 *
 * Mount once at the root (App.tsx). z-index: 4 (above Scene, below panels).
 */

import type { ReactElement } from 'react';
import './HudViewportCorners.css';

export function HudViewportCorners(): ReactElement {
  return (
    <>
      <div className="hud-corner tl" aria-hidden />
      <div className="hud-corner tr" aria-hidden />
      <div className="hud-corner bl" aria-hidden />
      <div className="hud-corner br" aria-hidden />
    </>
  );
}

export default HudViewportCorners;
