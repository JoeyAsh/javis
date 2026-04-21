/**
 * HudBloom — stub component, kept for API compatibility.
 *
 * The bloom effect is now implemented as a ::after pseudo-element on .hud-panel
 * in HudPanel.css (matching the prototype 1:1). This component renders nothing.
 */

import type { ReactElement } from 'react';

export interface HudBloomProps {
  className?: string;
}

export function HudBloom(_props: HudBloomProps): ReactElement {
  return <></>;
}

export default HudBloom;
