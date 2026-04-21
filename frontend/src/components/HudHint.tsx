/**
 * HudHint — bottom-right keyboard shortcut hint overlay.
 *
 * Displays the PUSH TO TALK (Space) and IDLE (Ctrl+.) shortcuts
 * as a non-interactive caption.
 */

import type { ReactElement } from 'react';
import './HudHint.css';

export function HudHint(): ReactElement {
  return (
    <div className="hud-hint" aria-hidden>
      PUSH TO TALK · <kbd>SPACE</kbd>&nbsp;&nbsp;IDLE · <kbd>CTRL+.</kbd>
    </div>
  );
}

export default HudHint;
