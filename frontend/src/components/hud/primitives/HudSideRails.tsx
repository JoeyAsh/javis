/**
 * HudSideRails — decorative vertical dashed rails on the left and right edges
 * of a HudPanel.
 *
 * Zero-prop component. Visibility is controlled by parent `.hud-panel` state
 * classes (hover / focused) via CSS in HudPanel.css.
 */

import type { ReactElement } from 'react';
import './HudSideRails.css';

/**
 * Renders two absolutely-positioned rail spans inside a `.hud-panel`.
 * Must be mounted as a direct child of the panel root `div` so the
 * `.hud-panel:hover` and `.hud-panel--focused` selectors can reach them.
 */
export function HudSideRails(): ReactElement {
  return (
    <>
      <span className="hud-rail hud-rail--left" aria-hidden />
      <span className="hud-rail hud-rail--right" aria-hidden />
    </>
  );
}

export default HudSideRails;
